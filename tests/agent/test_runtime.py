"""Integration tests for AgentRuntime and Interactive REPL commands."""

from pathlib import Path

import pytest

from pari.agent.runtime import AgentRuntime
from pari.fs.atomic import atomic_write, read_file
from pari.providers.base import LLMProvider, ModelResponse, ToolCall
from pari.providers.mock import MockOfflineProvider
from pari.tui.app import TerminalApp


@pytest.mark.asyncio
async def test_agent_runtime_turn_execution(tmp_path: Path):
    runtime = AgentRuntime(tmp_path, provider=MockOfflineProvider())
    session_id = runtime.start_session()
    assert session_id is not None

    # Test turn execution
    response = await runtime.execute_turn("Please find python files")
    assert "find_files" in response or "matches" in response or "PARI Agent" in response

    # Verify session log was written
    session_log = tmp_path / ".pari" / "session.jsonl"
    assert session_log.exists()
    assert session_log.stat().st_size > 0


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
                    tool_calls=[ToolCall("call_1", "read_file", {"path": "app.py"})],
                    stop_reason="tool_calls",
                )
            return ModelResponse(text="add returns the sum.", stop_reason="stop")

    runtime = AgentRuntime(tmp_path, provider=Scripted())
    text = await runtime.execute_turn("What does add return?")
    assert text == "add returns the sum."
    assert "[tools:" not in text
    assert runtime.provider.seen[1] == ["user", "assistant", "tool"]


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
