import asyncio
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pari.agent.runtime import AgentRuntime
from pari.fs.atomic import atomic_write, read_file
from pari.providers.base import LLMProvider
from pari.providers.message import ProviderMessage, ToolCall
from pari.providers.mock import MockOfflineProvider
from pari.providers.response import ModelResponse
from pari.session.logger import SessionLogger
from pari.tui.app import TerminalApp


@pytest.mark.asyncio
async def test_agent_runtime_turn_execution(tmp_path: Path):
    runtime = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    session_id = runtime.start_session()
    assert session_id is not None

    # Test turn execution
    response = await runtime.execute_turn("Please find python files")
    assert "find_files" in response or "matches" in response or "PARI Agent" in response

    # The checksummed DAG is the session log. The plain file is not written.
    assert runtime.session_file.exists()
    assert runtime.session_file.parent.name == "dags"
    assert "crc32" in runtime.session_file.read_text(encoding="utf-8")
    assert not (runtime.session_dir / "session.jsonl").exists()
    assert not (tmp_path / ".pari" / "session.jsonl").exists()


def test_session_output_lands_in_the_workspace_spool(tmp_path: Path):
    runtime = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    runtime.start_session()
    runtime._ensure_logger().append_event("TOOL_RESULT", {"output": "z" * 700})
    spool = tmp_path / ".pari" / "tool-outputs"
    files = list(spool.glob("*.txt"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == "z" * 700
    names = [path.name for path in runtime.session_dir.rglob("*")]
    assert "tool-outputs" not in names


@pytest.mark.asyncio
async def test_tool_result_is_sent_back_before_the_answer(tmp_path: Path):
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n")

    class Scripted(LLMProvider):
        def __init__(self):
            super().__init__("deepseek-chat", "k")
            self.seen: list[list[str]] = []
            self._step = 0

        async def complete(self, messages, tools=None, temperature=0.0):
            self.seen.append([message.role for message in messages])
            self._step += 1
            if self._step == 1:
                return ModelResponse(
                    text="reading",
                    tool_calls=[
                        ToolCall(
                            id="call_1", name="read_file", arguments={"path": "app.py"}
                        )
                    ],
                    stop_reason="tool_calls",
                )
            return ModelResponse(text="add returns the sum.", stop_reason="stop")

    runtime = AgentRuntime(tmp_path, provider=Scripted())
    text = await runtime.execute_turn("What does add return?")
    assert text == "add returns the sum."
    assert "[tools:" not in text
    assert runtime.provider.seen[1] == ["system", "user", "assistant", "tool"]


@pytest.mark.asyncio
async def test_system_prompt_names_the_workspace_and_git(tmp_path: Path):
    (tmp_path / ".git").mkdir()

    class Recording(LLMProvider):
        def __init__(self):
            super().__init__("deepseek-chat", "k")
            self.system: list[str] = []

        async def complete(self, messages, tools=None, temperature=0.0):
            self.system = [m.content for m in messages if m.role == "system"]
            return ModelResponse(text="ok", stop_reason="stop")

    provider = Recording()
    runtime = AgentRuntime(tmp_path, provider=provider)
    await runtime.execute_turn("push my changes")
    await runtime.execute_turn("again")
    assert len(provider.system) == 1
    prompt = provider.system[0]
    assert f"Workspace: {tmp_path.resolve()}" in prompt
    assert "is a git repository" in prompt
    assert "Do not prefix commands with cd" in prompt
    assert "Do not cd to /workspace or ~" in prompt
    assert "wait for the permission box" in prompt
    assert "pauses and asks the user" in prompt
    assert "Do not check gh auth" in prompt
    assert "open a pull request" in prompt


@pytest.mark.asyncio
async def test_system_prefix_stays_frozen_when_the_workspace_changes(
    tmp_path: Path,
):
    runtime = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    await runtime.execute_turn("hello")
    first = runtime.messages[0].content
    assert "not a git repository" in first
    (tmp_path / ".git").mkdir()
    (tmp_path / "note.txt").write_text("remember this\n", encoding="utf-8")
    await runtime.execute_turn("again")
    assert runtime.messages[0].content == first
    assert runtime.add_pinned_file("note.txt") is True
    updated = runtime.messages[0].content
    assert updated.startswith(first)
    assert "remember this" in updated
    runtime.reset_conversation()
    await runtime.execute_turn("fresh")
    assert "is a git repository" in runtime.messages[0].content


@pytest.mark.asyncio
async def test_repl_pings_the_frozen_system_prefix(tmp_path: Path):
    app = TerminalApp(tmp_path)
    await app.runtime.execute_turn("hello")
    frozen = app.runtime.messages[0].content
    provider = _PrefixRecorder()
    app.runtime.provider = provider
    app.runtime.warmer.interval_seconds = 0.01
    app.runtime.warmer.context_tokens = 300_000
    app.session = _IdlePrompt()
    await app.run_repl()
    assert frozen in provider.seen


class _PrefixRecorder(LLMProvider):
    def __init__(self) -> None:
        super().__init__("recorder")
        self.seen: list[str] = []

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        on_delta: Callable[[str], None] | None = None,
    ) -> ModelResponse:
        _ = tools, temperature, on_delta
        if messages and messages[0].role == "system":
            self.seen.append(messages[0].content)
        return ModelResponse(text=".", tokens_in=1, tokens_out=1)


class _IdlePrompt:
    def __init__(self) -> None:
        self.app = _EraseFlag()

    async def prompt_async(self, **_kwargs: object) -> str:
        await asyncio.sleep(0.08)
        return "/exit"


class _EraseFlag:
    erase_when_done = False


@pytest.mark.asyncio
async def test_slash_commands_in_terminal_app(tmp_path: Path):
    # Setup test file
    test_file = tmp_path / "hello.py"
    atomic_write(test_file, "val = 1\n")

    app = TerminalApp(tmp_path)
    # Test /help
    res = app.commands.handle("/help")
    assert res is not None
    assert "/undo" in res[1]

    # Test /model
    m_res = app.commands.handle("/model")
    assert "Active model" in m_res[1]

    # Test /add
    add_res = app.commands.handle("/add hello.py")
    assert "Added" in add_res[1]

    # Simulate edit and /undo
    app.runtime.undo_manager.record_snapshot("hello.py", "val = 1\n", "val = 2\n")
    atomic_write(test_file, "val = 2\n")

    undo_res = app.commands.handle("/undo")
    assert "hello.py" in undo_res[1] and "Reverted files" in undo_res[1]
    assert read_file(test_file) == "val = 1\n"
    app.runtime.undo_manager.record_side_effect("pip install requests")
    note = app.commands.handle("/undo")
    assert note is not None
    assert "Not reverted: pip install requests" in note[1]


@pytest.mark.asyncio
async def test_compaction_bounds_messages_over_100_turns(tmp_path: Path):
    class SyntheticMockProvider(LLMProvider):
        def __init__(self):
            super().__init__("mock", "key")
            self.sent_messages: list[list[ProviderMessage]] = []

        async def complete(
            self,
            messages: list[ProviderMessage],
            tools: list[dict[str, Any]] | None = None,
            temperature: float = 0.0,
            on_delta: Callable[[str], None] | None = None,
        ) -> ModelResponse:
            _ = tools, temperature, on_delta
            self.sent_messages.append([m.model_copy() for m in messages])
            tokens_in = sum(max(1, len(m.content) // 4) for m in messages)
            return ModelResponse(
                text=f"Ack turn {len(self.sent_messages)}",
                tool_calls=[],
                tokens_in=tokens_in,
                tokens_out=20,
                stop_reason="stop",
            )

    provider = SyntheticMockProvider()
    runtime = AgentRuntime(tmp_path, provider=provider, max_tokens=500)
    for i in range(100):
        await runtime.execute_turn(f"Synthetic prompt {i}")

    turn_100_messages = provider.sent_messages[99]
    # Without compaction, 100 turns would produce 201 messages.
    # With compaction, the message list sent on turn 100 is bounded.
    assert len(turn_100_messages) <= 25
    assert len(runtime.messages) <= 25


@pytest.mark.asyncio
async def test_pinned_file_content_appears_once_not_per_turn(tmp_path: Path):
    pinned_path = tmp_path / "pinned_spec.md"
    secret_marker = "UNIQUE_PINNED_CONTENT_ABC123"
    pinned_path.write_text(f"# Spec\n{secret_marker}\n")

    class CapturingProvider(LLMProvider):
        def __init__(self):
            super().__init__("mock", "key")
            self.sent_requests: list[list[ProviderMessage]] = []

        async def complete(
            self,
            messages: list[ProviderMessage],
            tools: list[dict[str, Any]] | None = None,
            temperature: float = 0.0,
            on_delta: Callable[[str], None] | None = None,
        ) -> ModelResponse:
            _ = tools, temperature, on_delta
            self.sent_requests.append([m.model_copy() for m in messages])
            return ModelResponse(
                text="ok",
                tool_calls=[],
                tokens_in=100,
                tokens_out=10,
                stop_reason="stop",
            )

    provider = CapturingProvider()
    runtime = AgentRuntime(tmp_path, provider=provider)
    assert runtime.add_pinned_file("pinned_spec.md") is True

    await runtime.execute_turn("first question")
    await runtime.execute_turn("second question")
    await runtime.execute_turn("third question")

    for req in provider.sent_requests:
        occurrences = sum(m.content.count(secret_marker) for m in req)
        assert occurrences == 1
        assert secret_marker in req[0].content
        for user_msg in req[1:]:
            assert secret_marker not in user_msg.content


@pytest.mark.asyncio
async def test_resume_restores_turns_after_a_torn_write(tmp_path: Path):
    runtime = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    await runtime.execute_turn("remember the codename bluebird")
    session_id = runtime.session_id
    assert session_id is not None
    with runtime.session_file.open("a", encoding="utf-8") as handle:
        handle.write('{"id": "killed-mid-write", "parentId": "')

    resumed = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    assert resumed.resume(session_id) == session_id
    contents = [message.content for message in resumed.messages]
    assert any("remember the codename bluebird" == text for text in contents)
    assert any("bluebird" in text and "PARI Agent" in text for text in contents)

    latest = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    assert latest.resume(None) == session_id


@pytest.mark.asyncio
async def test_resume_without_id_skips_a_newer_empty_session(tmp_path: Path):
    runtime = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    await runtime.execute_turn("remember the codename bluebird")
    real_id = runtime.session_id
    assert real_id is not None
    empty = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    empty.start_session()
    os.utime(runtime.session_file, (1_000, 1_000))
    os.utime(empty.session_file, (2_000, 2_000))

    resumed = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    assert resumed.resume(None) == real_id
    assert empty.session_id in {
        session_id for session_id, _prompt in resumed.list_sessions()
    }


@pytest.mark.asyncio
async def test_one_hundred_twenty_turns_write_two_checkpoints(tmp_path: Path):
    runtime = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    for index in range(120):
        await runtime.execute_turn(f"turn {index} marker")

    events = SessionLogger(runtime.session_file).read_events()
    checkpoints = [event for event in events if event["type"] == "CHECKPOINT_INDEX"]
    assert len(checkpoints) == 2
    first_chain = checkpoints[0]["data"]["ancestor_chain"]
    second_chain = checkpoints[1]["data"]["ancestor_chain"]
    assert checkpoints[0]["id"] in second_chain
    assert len(second_chain) > len(first_chain)

    resumed = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    resumed.resume(runtime.session_id)
    contents = [message.content for message in resumed.messages]
    assert any(text == "turn 0 marker" for text in contents)
    assert any(text == "turn 119 marker" for text in contents)
