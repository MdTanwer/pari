"""Unit tests for Layer 9 Interactive Terminal Application & REPL."""

from pathlib import Path

import pytest

from pari.providers.base import ProviderMessage
from pari.providers.openai import OpenAIProvider
from pari.tui.app import TerminalApp, _model_refusal


def test_tui_process_message_greeting(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)

    # Test variations of "hi how are you" / "hi howr you"
    assert app.process_message("hi how are you") == "Good! How can I help you today?"
    assert app.process_message("hi howr you") == "Good! How can I help you today?"
    assert app.process_message("how r you") == "Good! How can I help you today?"
    assert app.process_message("Hi How Are You?") == "Good! How can I help you today?"


@pytest.mark.asyncio
async def test_normal_prompt_runs_the_agent(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    text = await app.respond("Please find python files")
    assert "PARI Agent" in text
    assert app.process_message("Please find python files") is None


def test_tui_process_message_help(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    res = app.process_message("/help")
    assert "/help" in res
    assert "/exit" in res


def test_tui_slash_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PARI_AUTH_FILE", str(tmp_path / "missing-auth.json"))
    app = TerminalApp(workspace=tmp_path)

    # /diff command
    diff_res = app.process_message("/diff")
    assert "diff" in diff_res.lower()

    # /model command
    model_res = app.process_message("/model")
    assert "pari-core" in model_res

    switch_res = app.process_message("/model gpt-4o")
    assert "Sign in to OpenAI" in switch_res
    assert app.model_name == "pari-core"

    # /undo command
    undo_res = app.process_message("/undo")
    assert "undo" in undo_res.lower()

    # /add command with existing file
    test_file = tmp_path / "hello.py"
    test_file.write_text("print('test')")
    add_res = app.process_message(f"/add {test_file.name}")
    assert "Added" in add_res or "Pinned" in add_res
    missing = app.process_message("/add missing.py")
    assert "not found" in missing.lower()


def test_claude_model_is_selected_when_the_key_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    app = TerminalApp(workspace=tmp_path)
    switched = app.process_message("/model claude-3-7-sonnet-20250219")
    assert "claude-3-7-sonnet-20250219" in switched
    assert app.runtime.provider.model_name == "claude-3-7-sonnet-20250219"
    assert app.runtime.provider.api_key == "test-key"


@pytest.mark.asyncio
async def test_turn_updates_the_cost_meter(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    await app.respond("Please find python files")
    assert app.cost_meter.usage.input_tokens == 120
    assert app.cost_meter.usage.output_tokens == 40
    breakdown = app.process_message("/cost")
    assert "Input: 120" in breakdown
    assert "Output: 40" in breakdown


def test_snapshot_and_reset(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    app.runtime.messages.append(ProviderMessage(role="user", content="hello"))
    saved = app.process_message("/snapshot before-edit")
    assert "before-edit" in saved
    dag = tmp_path / ".pari" / "sessions" / f"{app.runtime.session_id}.jsonl"
    assert "snapshot" in dag.read_text(encoding="utf-8")

    cleared = app.process_message("/reset")
    assert "Conversation cleared" in cleared
    assert app.runtime.messages == []
    new_dag = tmp_path / ".pari" / "sessions" / f"{app.runtime.session_id}.jsonl"
    assert "session_start" in new_dag.read_text(encoding="utf-8")


def test_offline_model_does_not_require_sign_in(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    assert _model_refusal(app.model_name, app.runtime.provider) is None


def test_cloud_model_without_a_key_asks_for_sign_in():
    text = _model_refusal("gpt-4o", OpenAIProvider("gpt-4o", None))
    assert text is not None
    assert "pari-cli login openai --api-key" in text


@pytest.mark.asyncio
async def test_turn_limit_choice_continues_reverts_or_stops(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    app.runtime.awaiting_limit = True
    assert await app.apply_limit_choice("later") is None
    assert app.runtime.awaiting_limit is True

    continued = await app.apply_limit_choice("continue")
    assert continued is not None
    assert "PARI Agent" in continued
    assert app.runtime.awaiting_limit is False

    app.runtime.awaiting_limit = True
    assert await app.apply_limit_choice("stop") == "Stopped."
    assert app.runtime.awaiting_limit is False

    target = tmp_path / "hello.py"
    target.write_text("val = 2\n")
    app.runtime.undo_manager.record_snapshot("hello.py", "val = 1\n", "val = 2\n")
    app.runtime.awaiting_limit = True
    reverted = await app.apply_limit_choice("revert")
    assert reverted is not None
    assert "hello.py" in reverted
    assert target.read_text() == "val = 1\n"


def test_cost_meter():
    from pari.tui.status import CostMeter

    meter = CostMeter(model_family="pari-core")
    meter.add_usage(in_tokens=1000, out_tokens=500)
    assert meter.usage.total_tokens == 1500
    assert meter.calculate_cost_usd() > 0
    dated = CostMeter(model_family="claude-3-7-sonnet-20250219")
    dated.add_usage(in_tokens=1_000_000, out_tokens=0)
    assert dated.calculate_cost_usd() == pytest.approx(3.0)
    status = meter.format_status()
    assert "1.5k tokens" in status
    assert "$" in status


def test_slash_command_completer():
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

    from pari.tui.app import SlashCommandCompleter

    completer = SlashCommandCompleter()
    event = CompleteEvent(completion_requested=False)

    # Typing '/' lists every slash command, including the session ones.
    doc_slash = Document("/")
    completions = list(completer.get_completions(doc_slash, event))
    texts = [c.text for c in completions]
    commands = [
        "/help",
        "/diff",
        "/undo",
        "/clear",
        "/model",
        "/add",
        "/snapshot",
        "/cost",
        "/reset",
        "/login",
        "/logout",
        "/exit",
        "/quit",
    ]
    assert len(completions) == len(commands)
    for cmd in commands:
        assert cmd in texts
        # Ensure display and display_meta description exist
        comp = next(c for c in completions if c.text == cmd)
        assert comp.display_meta != ""
        assert comp.start_position == -1

    # 2. Specific prefix matching
    doc_diff = Document("/di")
    diff_comps = list(completer.get_completions(doc_diff, event))
    assert len(diff_comps) == 1
    assert diff_comps[0].text == "/diff"
    assert diff_comps[0].start_position == -3

    doc_model = Document("/mo")
    model_comps = list(completer.get_completions(doc_model, event))
    assert len(model_comps) == 1
    assert model_comps[0].text == "/model"

    # 3. Non-slash commands should not trigger completions
    doc_text = Document("Hello PARI")
    assert list(completer.get_completions(doc_text, event)) == []

    # 4. Commands with arguments should not trigger slash command completions
    doc_args = Document("/model gpt-4o")
    assert list(completer.get_completions(doc_args, event)) == []
