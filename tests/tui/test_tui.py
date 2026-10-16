"""Unit tests for Layer 9 Interactive Terminal Application & REPL."""

import re
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from prompt_toolkit import PromptSession
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from pari.providers.base import LLMProvider
from pari.providers.exceptions import ProviderError
from pari.providers.message import ProviderMessage, ToolCall
from pari.providers.openai import OpenAIProvider
from pari.providers.response import ModelResponse
from pari.routing.router import DualModelRouter, router_for
from pari.tui.activity import preview
from pari.tui.app import TerminalApp, _model_refusal
from pari.tui.errors import model_error_text
from pari.tui.keys import EXPAND, create_key_bindings
from pari.tui.status import CostMeter
from pari.tui.transcript import transcript_viewer


_PROVIDER_KEY_ENV = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "XAI_API_KEY",
    "OPENROUTER_API_KEY",
)


@pytest.fixture(autouse=True)
def _isolated_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every test off the developer's real sign-in store and API keys."""
    monkeypatch.setenv("PARI_AUTH_FILE", str(tmp_path / "auth.json"))
    for name in _PROVIDER_KEY_ENV:
        monkeypatch.delenv(name, raising=False)


def _toolbar_text(app: TerminalApp) -> str:
    return "".join(piece for _, piece in app._toolbar())


_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# The live spinner redraws itself: "<label>… <seconds>s". Match that shape
# exactly so a real summary row is never dropped by accident.
_SPINNER = re.compile(r"…\s+\d+s$")


def _plain(output: str) -> str:
    """Drop terminal control codes so assertions see the text a person reads."""
    return _ANSI.sub("", output)


def _visible_rows(output: str) -> list[str]:
    """Summary rows from the last redraw, without the live spinner."""
    plain = _plain(output.rsplit("\x1b[J", 1)[-1])
    rows = []
    for line in plain.splitlines():
        line = line.strip()
        if not line or _SPINNER.search(line):
            continue
        rows.append(line)
    return rows


def test_greetings_are_model_turns(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    for text in ("hi", "hello", "hey", "hi how are you", "Hi How Are You?"):
        assert app.process_message(text) is None


async def test_greeting_reaches_the_model(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    text = await app.respond("hi")
    # The offline mock echoes the prompt; a greeting is a normal model turn.
    assert text == "PARI Agent response to: hi"


def test_access_rejection_shows_the_provider_message():
    text = model_error_text(
        ProviderError(
            "OpenAI",
            status_code=401,
            code="no_matching_rule",
            detail="Unauthorized",
            error_type="rejected_by_access_enforcement",
        )
    )
    assert text == (
        "Model error\n"
        "Code: Authentication\n"
        "\n"
        "Detail:\n"
        "Unauthorized\n"
        "rejected_by_access_enforcement\n"
        "no_matching_rule"
    )


def test_timeout_and_rate_limit_keep_the_provider_detail():
    timeout = model_error_text(ProviderError("OpenAI", kind="timeout"))
    assert "Code: Timeout" in timeout
    assert "OpenAI did not respond in time." in timeout
    assert "What to try" not in timeout
    limited = model_error_text(
        ProviderError("OpenAI", status_code=429, detail="slow down")
    )
    assert "Code: RateLimit" in limited
    assert "Detail:\nslow down" in limited
    assert "What to try" not in limited


class _Rejecting(LLMProvider):
    def __init__(self) -> None:
        super().__init__("gpt-4o", api_key="token")

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        on_delta: Any = None,
    ) -> ModelResponse:
        _ = messages, tools, temperature, on_delta
        raise ProviderError(
            "OpenAI",
            status_code=401,
            code="no_matching_rule",
            detail="Unauthorized",
            error_type="rejected_by_access_enforcement",
        )


async def test_provider_failure_stays_in_the_session(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    offline = app.runtime.provider
    offline_router = app.runtime.router
    app.model_name = "gpt-4o"
    app.runtime.provider = _Rejecting()
    app.runtime.router = router_for(app.runtime.provider)
    text = await app.respond("read my project repo")
    assert "Code: Authentication" in text
    assert "Unauthorized" in text
    assert "rejected_by_access_enforcement" in text
    assert "no_matching_rule" in text
    assert "What to try" not in text
    assert "Traceback" not in text
    assert app.runtime.messages == []
    assert app.cost_meter.usage.total_tokens == 0
    app.model_name = "pari-core"
    app.runtime.provider = offline
    app.runtime.router = offline_router
    follow = await app.respond("hi")
    assert "PARI Agent response to:" in follow


async def test_turn_returns_to_the_prompt_after_a_provider_failure(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    app.runtime.provider = _Rejecting()
    app.runtime.router = router_for(app.runtime.provider)
    assert await app._turn("read my project repo") is True


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


def test_tui_slash_commands(tmp_path: Path):
    # The autouse fixture leaves no OpenAI key and no saved sign-in.
    app = TerminalApp(workspace=tmp_path)

    # /diff command: a clean workspace has nothing to show.
    assert app.process_message("/diff") == "No uncommitted diff."

    # /model command
    model_res = app.process_message("/model")
    assert model_res == (
        "Active model: `pari-core` "
        "(Tiers: openai, deepseek, anthropic, grok, openrouter, pari-core)"
    )

    switch_res = app.process_message("/model gpt-4o")
    assert "Sign in to OpenAI" in switch_res
    assert app.model_name == "pari-core"

    # /undo command: nothing recorded yet.
    assert app.process_message("/undo") == (
        "No previous file modifications in session history to undo."
    )

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


async def test_turn_updates_the_cost_meter(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    await app.respond("Please find python files")
    # 120/40 are the counts MockOfflineProvider reports for a "find" prompt.
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


class _Scripted(LLMProvider):
    """Narrate, read app.py, then answer."""

    def __init__(self) -> None:
        super().__init__("pari-core", "offline")
        self._step = 0

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        on_delta: Any = None,
    ) -> ModelResponse:
        _ = messages, tools, temperature
        self._step += 1
        if self._step == 1:
            text = "Reading the function."
            if on_delta is not None:
                on_delta(text)
            return ModelResponse(
                text=text,
                tool_calls=[
                    ToolCall(
                        id="call_1", name="read_file", arguments={"path": "app.py"}
                    )
                ],
                stop_reason="tool_calls",
            )
        text = "Checking the body.\nadd returns the sum."
        if on_delta is not None:
            on_delta(text)
        return ModelResponse(text=text, stop_reason="stop")


def _scripted_app(tmp_path: Path, console: Console) -> TerminalApp:
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n")
    app = TerminalApp(tmp_path)
    provider = _Scripted()
    app.runtime.provider = provider
    app.runtime.router = DualModelRouter.from_providers(provider, provider)
    app.console = console
    return app


async def test_turn_shows_a_summary_then_the_answer(tmp_path: Path):
    buffer = StringIO()
    app = _scripted_app(tmp_path, Console(file=buffer, force_terminal=False, width=80))
    await app._turn("What does add return?")
    printed = buffer.getvalue()
    assert printed.index("Reading the function.") < printed.index("Explored 1 file")
    assert printed.index("Explored 1 file") < printed.index("add returns the sum.")
    assert "def add" not in printed
    assert "ctrl+o to expand" in _toolbar_text(app)

    buffer.seek(0)
    buffer.truncate(0)
    await app.show_activity()
    transcript = buffer.getvalue()
    assert "▾ read_file  app.py" in transcript
    assert "def add" in transcript
    assert "Checking the body." in transcript


async def test_summary_stays_a_few_rows_however_long_the_turn(tmp_path: Path):
    """A short block can always be erased, so it is never printed twice."""
    buffer = StringIO()
    app = TerminalApp(tmp_path)
    app.console = Console(file=buffer, force_terminal=True, width=60, height=20)
    for number in range(40):
        name = "bash" if number % 2 else "read_file"
        args = {"command": f"echo {number}"} if name == "bash" else {"path": "a.py"}
        app._show_delta(f"Step {number}: looking at the next thing in detail.\n")
        app._show_tool_call(name, args)
        result = '{"exit_code": 0, "output": "ok"}' if name == "bash" else "text"
        app._show_tool_result(
            ToolCall(id=str(number), name=name, arguments=args), text=result
        )
    app._end_wait()
    rows = _visible_rows(buffer.getvalue())
    assert len(rows) <= 6
    assert all(len(row) < 60 for row in rows)
    assert any("more actions" in row for row in rows)
    assert "Step 3" not in "\n".join(rows)


def test_spinner_says_what_the_running_tool_is_doing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TERM", "xterm-256color")
    app = TerminalApp(tmp_path)
    cases = [
        ("bash", {"command": "pytest -q"}, "Running pytest -q"),
        ("read_file", {"path": "app.py"}, "Exploring app.py"),
        ("grep_search", {"query": "TODO"}, "Searching TODO"),
        ("edit_file", {"path": "app.py"}, "Editing app.py"),
    ]
    for name, arguments, label in cases:
        buffer = StringIO()
        app.console = Console(file=buffer, force_terminal=True, width=80)
        app._show_tool_call(name, arguments)
        # The first spinner frame is drawn on start(), so no sleep is needed.
        app._end_wait()
        painted = _plain(buffer.getvalue())
        assert f"{label}… 0s" in painted


def test_command_output_stays_hidden_until_expanded(tmp_path: Path):
    buffer = StringIO()
    app = TerminalApp(tmp_path)
    app.console = Console(file=buffer, force_terminal=True, width=60)
    call = ToolCall(id="1", name="bash", arguments={"command": "ls -la"})
    app._show_tool_call("bash", call.arguments)
    app._show_output_delta("stdout", "secret listing\n")
    app._show_tool_result(call, '{"exit_code": 2, "output": "secret listing\\n"}')
    app._end_wait()
    painted = _plain(buffer.getvalue())
    assert "Ran 1 command, 1 failed" in painted
    assert "secret listing" not in painted
    transcript = app._log.transcript()
    assert "▾ bash  exit 2" in transcript
    assert "$ ls -la" in transcript
    assert "secret listing" in transcript


async def test_ctrl_o_asks_for_the_transcript_only_after_a_tool_ran():
    for ran, expected in ((True, EXPAND), (False, "")):
        with create_pipe_input() as pipe:
            session = PromptSession(
                input=pipe,
                output=DummyOutput(),
                key_bindings=create_key_bindings(lambda ran=ran: ran),
            )
            pipe.send_text("\x0f\r")
            assert await session.prompt_async() == expected


def test_transcript_viewer_closes_on_ctrl_o():
    with create_pipe_input() as pipe:
        viewer = transcript_viewer("▾ bash  exit 0\n$ ls")
        viewer.input = pipe
        viewer.output = DummyOutput()
        pipe.send_text("\x0f")
        viewer.run()
        # ctrl+o exits the viewer; a hung app would never reach this line.
        assert not viewer.is_running


def test_bash_result_keeps_output_out_of_the_summary(tmp_path: Path):
    buffer = StringIO()
    app = TerminalApp(tmp_path)
    app.console = Console(file=buffer, force_terminal=False, width=80)
    call = ToolCall(id="1", name="bash", arguments={"command": "echo hello"})
    app._show_tool_call("bash", call.arguments)
    app._show_tool_result(
        call, '{"exit_code": 0, "output": "hello\\n", "sidecar_path": "/tmp/x"}'
    )
    app._settle()
    printed = buffer.getvalue()
    assert "Ran 1 command" in printed
    assert "hello" not in printed.replace("echo hello", "")
    transcript = app._log.transcript()
    assert "▾ bash  exit 0" in transcript
    assert "sidecar_path" not in transcript


def test_preview_keeps_the_start_of_a_long_result():
    text = "\n".join(f"line {number}" for number in range(30))
    shown = preview(text, lines=5, chars=2000)
    assert "line 0" in shown
    assert "line 4" in shown
    assert "line 29" not in shown
    assert "25 more lines" in shown


def test_limit_choice_menu_lists_the_three_actions():
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document

    from pari.tui.completer import LimitChoiceCompleter

    completer = LimitChoiceCompleter()
    event = CompleteEvent(completion_requested=True)
    labels = [item.text for item in completer.get_completions(Document(""), event)]
    assert labels == ["Continue", "Revert", "Stop"]
    narrowed = list(completer.get_completions(Document("r"), event))
    assert [item.text for item in narrowed] == ["Revert"]


def test_limit_prompt_does_not_reuse_the_chat_session(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    assert app.limit_session is not app.session
    assert app.limit_session.placeholder is None
    assert app.session.completer is not app.limit_session.completer


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

    # A prefix narrows the list to the one matching command.
    doc_diff = Document("/di")
    diff_comps = list(completer.get_completions(doc_diff, event))
    assert len(diff_comps) == 1
    assert diff_comps[0].text == "/diff"
    assert diff_comps[0].start_position == -3

    doc_model = Document("/mo")
    model_comps = list(completer.get_completions(doc_model, event))
    assert len(model_comps) == 1
    assert model_comps[0].text == "/model"

    # Plain text does not trigger completions.
    doc_text = Document("Hello PARI")
    assert list(completer.get_completions(doc_text, event)) == []

    # Once a space is typed the command name is finished; the menu stays closed.
    doc_args = Document("/model gpt-4o")
    assert list(completer.get_completions(doc_args, event)) == []
