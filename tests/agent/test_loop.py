"""Double-while execution loop guards."""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from pari.agent.guards import LENGTH_TRUNCATION_NOTICE
from pari.agent.loop import AgentExecutionLoop
from pari.agent.reflection import ReflectionManager
from pari.agent.runtime import AgentRuntime
from pari.providers.base import LLMProvider
from pari.providers.message import ProviderMessage, ToolCall
from pari.providers.response import ModelResponse
from pari.session.undo import GuardedUndoManager


class ScriptedProvider(LLMProvider):
    def __init__(self, responses: list[ModelResponse]):
        super().__init__("scripted")
        self._responses = list(responses)

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        _ = messages, tools, temperature
        return self._responses.pop(0)


class RecordingRegistry:
    def __init__(self, result: Any = "ok", error: Exception | None = None):
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._result = result
        self._error = error

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        if self._error is not None:
            raise self._error
        return self._result


def _not_truncated(_step: object) -> bool:
    return False


@pytest.mark.asyncio
async def test_plain_answer_ends_the_turn():
    async def step(_prompt: str, _turn: int) -> str:
        return "plain answer"

    result = await AgentExecutionLoop().run_turn("hi", step, _not_truncated)
    assert result.response_text == "plain answer"
    assert result.tool_calls_executed == 0
    assert result.requires_user_input is False


@pytest.mark.asyncio
async def test_length_stop_does_not_run_tools():
    registry = RecordingRegistry()
    replies = [
        ModelResponse(
            text="partial edit",
            tool_calls=[
                ToolCall(
                    id="1",
                    name="write_file",
                    arguments={"path": "bad.txt", "content": "x"},
                )
            ],
            stop_reason="length",
            tokens_out=4,
        ),
        ModelResponse(text="stopped cleanly", stop_reason="end_turn", tokens_out=2),
    ]

    async def step(_prompt: str, _turn: int) -> ModelResponse:
        return replies.pop(0)

    loop = AgentExecutionLoop(registry=registry)
    result = await loop.run_turn("edit the file", step, _not_truncated)
    assert registry.calls == []
    assert result.response_text == "stopped cleanly"
    assert result.tool_calls_executed == 0
    assert result.tokens_used == 6


@pytest.mark.asyncio
async def test_turn_limit_asks_the_user():
    registry = RecordingRegistry()

    async def step(_prompt: str, turn: int) -> ModelResponse:
        return ModelResponse(
            text="again",
            tool_calls=[
                ToolCall(id=str(turn), name="bash", arguments={"command": "true"})
            ],
            stop_reason="end_turn",
        )

    loop = AgentExecutionLoop(max_autonomous_turns=2, registry=registry)
    result = await loop.run_turn("keep going", step, _not_truncated)
    assert result.requires_user_input is True
    assert "Turn limit reached" in result.response_text
    assert result.tool_calls_executed == 2


@pytest.mark.asyncio
async def test_reflection_stops_after_the_budget():
    registry = RecordingRegistry(error=RuntimeError("syntax error"))

    async def step(_prompt: str, _turn: int) -> ModelResponse:
        return ModelResponse(
            text="edit",
            tool_calls=[ToolCall(id="1", name="edit_file", arguments={"path": "a.py"})],
            stop_reason="end_turn",
        )

    loop = AgentExecutionLoop(
        registry=registry,
        reflection=ReflectionManager(max_reflections=1),
    )
    result = await loop.run_turn("fix it", step, _not_truncated)
    assert result.requires_user_input is True
    assert "Reflection limit reached" in result.response_text
    assert result.tool_calls_executed == 0


@pytest.mark.asyncio
async def test_timed_out_command_is_reported_as_a_daemon():
    registry = RecordingRegistry(
        result={
            "timed_out": True,
            "output": "listening",
            "exit_code": 124,
            "timeout": 30,
            "idle_seconds": 10,
        }
    )
    seen: list[str] = []

    async def step(prompt: str, turn: int) -> ModelResponse:
        seen.append(prompt)
        if turn == 1:
            return ModelResponse(
                text="start",
                tool_calls=[
                    ToolCall(id="1", name="bash", arguments={"command": "npm run dev"})
                ],
                stop_reason="end_turn",
            )
        return ModelResponse(text="noted", stop_reason="end_turn")

    loop = AgentExecutionLoop(registry=registry)
    result = await loop.run_turn("start the server", step, _not_truncated)
    assert "DAEMON DETECTED" in seen[1]
    assert "was stopped after 10s" in seen[1]
    assert "npm run dev" in seen[1]
    assert "separate terminal" in seen[1]
    assert "background" not in seen[1]
    assert result.response_text == "noted"
    assert result.tool_calls_executed == 1


@pytest.mark.asyncio
async def test_runtime_discards_a_truncated_write(tmp_path: Path):
    provider = ScriptedProvider(
        [
            ModelResponse(
                text="cut off",
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="write_file",
                        arguments={"path": "bad.txt", "content": "should not land"},
                    )
                ],
                stop_reason="length",
            ),
            ModelResponse(text="stopped cleanly", stop_reason="end_turn"),
        ]
    )
    runtime = AgentRuntime(tmp_path, provider=provider)
    response = await runtime.execute_turn("write a file")
    assert response == "stopped cleanly"
    assert not (tmp_path / "bad.txt").exists()
    assert LENGTH_TRUNCATION_NOTICE in runtime.messages[1].content or any(
        LENGTH_TRUNCATION_NOTICE in message.content for message in runtime.messages
    )


@pytest.mark.asyncio
async def test_runtime_applies_a_tool_then_answers(tmp_path: Path):
    provider = ScriptedProvider(
        [
            ModelResponse(
                text="writing",
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="write_file",
                        arguments={"path": "hello.txt", "content": "Hello loop"},
                    )
                ],
                stop_reason="end_turn",
            ),
            ModelResponse(text="wrote the file", stop_reason="end_turn"),
        ]
    )
    runtime = AgentRuntime(tmp_path, provider=provider)
    response = await runtime.execute_turn("create hello.txt")
    assert response == "wrote the file"
    assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "Hello loop"
    runtime.undo_manager.undo()
    assert not (tmp_path / "hello.txt").exists()


@pytest.mark.asyncio
async def test_syntax_error_is_sent_back_as_a_lint_block(tmp_path: Path):
    provider = ScriptedProvider(
        [
            ModelResponse(
                text="writing",
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="write_file",
                        arguments={"path": "a.py", "content": "def f(:\n"},
                    )
                ],
                stop_reason="end_turn",
            ),
            ModelResponse(text="will fix", stop_reason="end_turn"),
        ]
    )
    runtime = AgentRuntime(tmp_path, provider=provider)
    response = await runtime.execute_turn("add a function")
    assert response == "will fix"
    assert any("[LINT ERROR]" in message.content for message in runtime.messages)
    assert (tmp_path / "a.py").exists()


@pytest.mark.asyncio
async def test_turn_warning_is_not_placed_in_the_prompt():
    warnings: list[str] = []
    seen: list[str] = []

    async def step(prompt: str, turn: int) -> ModelResponse:
        seen.append(prompt)
        return ModelResponse(
            text="again",
            tool_calls=[
                ToolCall(id=str(turn), name="bash", arguments={"command": "true"})
            ],
            stop_reason="end_turn",
        )

    loop = AgentExecutionLoop(
        max_autonomous_turns=30,
        registry=RecordingRegistry(),
        on_warning=warnings.append,
    )
    result = await loop.run_turn("go", step, _not_truncated)
    assert warnings == ["Turn 30 of 30."]
    assert result.warning == "Turn 30 of 30."
    assert all("Turn 30" not in prompt for prompt in seen)


@pytest.mark.asyncio
async def test_turn_limit_captures_the_git_diff(tmp_path: Path):
    _git(tmp_path, "init")
    tracked = tmp_path / "notes.txt"
    tracked.write_text("before\n")
    _git(tmp_path, "add", "notes.txt")
    _git(
        tmp_path,
        "-c",
        "user.email=dev@pari.dev",
        "-c",
        "user.name=pari",
        "commit",
        "-m",
        "init",
    )
    tracked.write_text("after\n")
    seen: list[str] = []

    async def step(_prompt: str, turn: int) -> ModelResponse:
        return ModelResponse(
            text="again",
            tool_calls=[
                ToolCall(id=str(turn), name="bash", arguments={"command": "true"})
            ],
            stop_reason="end_turn",
        )

    loop = AgentExecutionLoop(
        max_autonomous_turns=1,
        registry=RecordingRegistry(),
        workspace=tmp_path,
        on_diff=lambda _name, diff: seen.append(diff),
    )
    result = await loop.run_turn("go", step, _not_truncated)
    assert result.requires_user_input is True
    assert "Turn limit reached" in result.response_text
    assert "-before" in result.diff
    assert "+after" in result.diff
    assert seen and "-before" in seen[0]


@pytest.mark.asyncio
async def test_successful_package_install_is_disclosed_on_undo(tmp_path: Path):
    undo = GuardedUndoManager(tmp_path)
    command = "pip install requests"

    async def step(_prompt: str, turn: int) -> ModelResponse:
        if turn > 1:
            return ModelResponse(text="installed", stop_reason="end_turn")
        return ModelResponse(
            text="installing",
            tool_calls=[
                ToolCall(id="1", name="bash", arguments={"command": command}),
            ],
            stop_reason="tool_use",
        )

    loop = AgentExecutionLoop(
        registry=RecordingRegistry({"exit_code": 0, "stdout": ""}),
        undo=undo,
        workspace=tmp_path,
    )
    await loop.run_turn("install requests", step, _not_truncated)
    result = undo.undo()
    assert result.disclosed_side_effects == [command]
    assert result.reverted_files == []


@pytest.mark.asyncio
async def test_failed_install_and_plain_bash_are_not_side_effects(tmp_path: Path):
    undo = GuardedUndoManager(tmp_path)

    async def step(_prompt: str, turn: int) -> ModelResponse:
        if turn > 1:
            return ModelResponse(text="done", stop_reason="end_turn")
        return ModelResponse(
            text="running",
            tool_calls=[
                ToolCall(
                    id="1",
                    name="bash",
                    arguments={"command": "pip install requests"},
                ),
            ],
            stop_reason="tool_use",
        )

    failed = AgentExecutionLoop(
        registry=RecordingRegistry({"exit_code": 1, "stdout": ""}),
        undo=undo,
        workspace=tmp_path,
    )
    await failed.run_turn("install requests", step, _not_truncated)
    plain = AgentExecutionLoop(
        registry=RecordingRegistry({"exit_code": 0, "stdout": "hi"}),
        undo=undo,
        workspace=tmp_path,
    )

    async def echo(_prompt: str, turn: int) -> ModelResponse:
        if turn > 1:
            return ModelResponse(text="done", stop_reason="end_turn")
        return ModelResponse(
            text="running",
            tool_calls=[
                ToolCall(id="2", name="bash", arguments={"command": "echo hi"}),
            ],
            stop_reason="tool_use",
        )

    await plain.run_turn("say hi", echo, _not_truncated)
    assert undo.undo().disclosed_side_effects == []


def _write(path: str, content: str) -> ModelResponse:
    return ModelResponse(
        text="writing",
        tool_calls=[
            ToolCall(
                id="1",
                name="write_file",
                arguments={"path": path, "content": content},
            )
        ],
        stop_reason="end_turn",
    )


def _done(text: str) -> ModelResponse:
    return ModelResponse(text=text, stop_reason="end_turn")


@pytest.mark.asyncio
async def test_undo_removes_a_file_the_turn_created(tmp_path: Path):
    runtime = AgentRuntime(
        tmp_path,
        provider=ScriptedProvider([_write("new.txt", "hi\n"), _done("created")]),
    )
    await runtime.execute_turn("create new.txt")
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "hi\n"
    runtime.undo_manager.undo()
    assert not (tmp_path / "new.txt").exists()


@pytest.mark.asyncio
async def test_undo_restores_the_original_after_two_edits(tmp_path: Path):
    target = tmp_path / "a.py"
    target.write_text("original\n", encoding="utf-8")
    runtime = AgentRuntime(
        tmp_path,
        provider=ScriptedProvider(
            [
                ModelResponse(
                    text="editing",
                    tool_calls=[
                        ToolCall(
                            id="1",
                            name="write_file",
                            arguments={"path": "a.py", "content": "middle\n"},
                        ),
                        ToolCall(
                            id="2",
                            name="write_file",
                            arguments={"path": "a.py", "content": "final\n"},
                        ),
                    ],
                    stop_reason="end_turn",
                ),
                _done("edited"),
            ]
        ),
    )
    await runtime.execute_turn("edit a.py twice")
    assert target.read_text(encoding="utf-8") == "final\n"
    runtime.undo_manager.undo()
    assert target.read_text(encoding="utf-8") == "original\n"


@pytest.mark.asyncio
async def test_undo_reverts_only_the_latest_turn(tmp_path: Path):
    runtime = AgentRuntime(
        tmp_path,
        provider=ScriptedProvider(
            [
                _write("a.py", "from a\n"),
                _done("wrote a"),
                _write("b.py", "from b\n"),
                _done("wrote b"),
            ]
        ),
    )
    await runtime.execute_turn("create a.py")
    await runtime.execute_turn("create b.py")
    runtime.undo_manager.undo()
    assert not (tmp_path / "b.py").exists()
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "from a\n"
    runtime.undo_manager.undo()
    assert not (tmp_path / "a.py").exists()


def _git(workspace: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
