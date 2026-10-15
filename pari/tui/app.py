"""REPL loop.

Slash commands, the completion menu, key bindings, and the prompt chrome live
in the neighbouring modules. This file owns the session and decides whether a
line is a local command or a model turn.
"""

import json
import sys
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.application.current import get_app
from prompt_toolkit.document import Document
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.validation import ValidationError, Validator
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.text import Text

from pari.agent.runtime import AgentRuntime
from pari.auth.interactive import login_tty, logout_tty
from pari.auth.login import sign_in_hint
from pari.auth.providers import info_for_model
from pari.providers.base import LLMProvider
from pari.providers.exceptions import ProviderError
from pari.providers.message import ToolCall
from pari.providers.mock import MockOfflineProvider
from pari.session.undo import UndoResult
from pari.tools.bash import BashTool
from pari.tui.activity import Action, TurnLog
from pari.tui.completer import LimitChoiceCompleter, SlashCommandCompleter
from pari.tui.errors import model_error_text
from pari.tui.keys import EXPAND, create_key_bindings, create_limit_key_bindings
from pari.tui.prompt import (
    placeholder_tokens,
    prompt_tokens,
    toolbar_tokens,
    welcome_panel,
)
from pari.tui.slash import SessionCommands
from pari.tui.status import CostMeter
from pari.tui.style import CLI_STYLE
from pari.tui.transcript import transcript_viewer


__all__ = ["SlashCommandCompleter", "TerminalApp"]


class TerminalApp:
    """One workspace session: prompt, local commands, then the agent runtime."""

    def __init__(
        self,
        workspace: Path,
        model_name: str = "pari-core",
        edit_fallback: str = "none",
        repomap: str = "off",
        sandbox_mode: str | None = None,
    ):
        self.workspace = workspace.resolve()
        self.model_name = model_name
        self.edit_fallback = edit_fallback
        self.console = Console()
        # pari-core stays the offline mock. A claude name selects Anthropic.
        self.runtime = AgentRuntime(
            self.workspace,
            model_name=model_name,
            edit_fallback=edit_fallback,
            repomap=repomap,
            sandbox_mode=sandbox_mode,
        )
        self.cost_meter = CostMeter(model_family=model_name)
        self.commands = SessionCommands(self)
        # Text printed live before the first tool of the turn.
        self._streamed = ""
        self._log = TurnLog()
        self._tail_lines = 0
        self._paint_lock = threading.Lock()
        self._activity: Status | None = None
        bash = self.runtime.tools.get("bash")
        if isinstance(bash, BashTool):
            bash.on_output = self._show_output_delta
        self.session: PromptSession = PromptSession(
            history=InMemoryHistory(),
            completer=SlashCommandCompleter(),
            style=CLI_STYLE,
            complete_while_typing=True,
            complete_style=CompleteStyle.COLUMN,
            reserve_space_for_menu=10,
            key_bindings=create_key_bindings(lambda: bool(self._log.actions)),
        )
        # A second session so this menu does not keep the chat placeholder.
        self.limit_session: PromptSession = PromptSession(
            completer=LimitChoiceCompleter(),
            style=CLI_STYLE,
            validator=_LimitValidator(),
            complete_while_typing=True,
            complete_style=CompleteStyle.COLUMN,
            reserve_space_for_menu=6,
            key_bindings=create_limit_key_bindings(),
        )

    def print_welcome(self) -> None:
        self.console.print(welcome_panel(self.workspace, self.model_name))

    def process_message(self, user_msg: str) -> str | None:
        """Return a local answer, or None when the line should run a model turn."""
        quick = self.commands.handle(user_msg)
        if quick is not None:
            return quick[1]
        return None

    async def respond(self, user_msg: str) -> str:
        """Answer a slash command locally, or run one agent turn."""
        quick = self.process_message(user_msg)
        if quick is not None:
            return quick
        blocked = _model_refusal(self.model_name, self.runtime.provider)
        if blocked is not None:
            return blocked
        return await self._model_turn(self._execute(user_msg))

    async def _model_turn(self, turn: Awaitable[str]) -> str:
        """Run one model call. A provider failure stays in the session."""
        self._begin_wait()
        try:
            text = await turn
        except ProviderError as exc:
            return model_error_text(exc)
        finally:
            self._end_wait()
            self._settle()
        self.cost_meter.add_usage(
            self.runtime.tokens_in,
            self.runtime.tokens_out,
            self.runtime.cached_tokens,
        )
        if self.runtime.turn_warning:
            return f"{self.runtime.turn_warning}\n\n{text}"
        return text

    async def run_repl(self) -> None:
        """Read lines until the user exits or the terminal closes."""
        self.print_welcome()
        draft = ""
        while True:
            try:
                user_input = await self.session.prompt_async(
                    message=prompt_tokens,
                    placeholder=placeholder_tokens,
                    bottom_toolbar=self._toolbar,
                    default=draft,
                )
                self.session.app.erase_when_done = False
                draft = ""
                if user_input == EXPAND:
                    draft = self.session.default_buffer.text
                    await self.show_activity()
                    continue
                text = user_input.strip()
                if not text:
                    continue
                if not await self._turn(text):
                    break
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[dim]Session interrupted. Goodbye![/dim]")
                break

    async def _turn(self, text: str) -> bool:
        """Handle one line. Return False when the session should stop."""
        if text in ("/exit", "/quit", "exit", "quit"):
            self.console.print("[dim]Exiting PARI session. Goodbye![/dim]")
            return False
        # These menus draw on the raw terminal, so they stay outside the panel.
        if text == "/login":
            login_tty()
            return True
        if text == "/logout":
            logout_tty()
            return True
        if text == "/clear":
            self.console.clear()
            self.print_welcome()
            return True
        self._streamed = ""
        self._log = TurnLog()
        response = await self.respond(text)
        self._show_answer(response)
        if self.runtime.awaiting_limit:
            follow = await self._ask_limit()
            if follow:
                self._print_reply(follow)
        return True

    async def apply_limit_choice(self, choice: str) -> str | None:
        """Continue, revert, or stop. None means the choice was not one of those."""
        action = _limit_action(choice)
        if action is None:
            return None
        if action == "continue":
            return await self._model_turn(
                self.runtime.continue_turn(**self._live_callbacks())
            )
        self.runtime.awaiting_limit = False
        if action == "revert":
            return _revert_message(self.runtime.undo_manager.undo())
        return "Stopped."

    async def _ask_limit(self) -> str:
        """Ask until the user picks Continue, Revert, or Stop."""
        if not sys.stdin.isatty():
            self.runtime.awaiting_limit = False
            return "Stopped."
        while self.runtime.awaiting_limit:
            choice = await self.limit_session.prompt_async(
                message=[("class:prompt", "Continue, Revert, or Stop? ")],
                pre_run=_open_limit_menu,
                bottom_toolbar=lambda: toolbar_tokens(
                    self.workspace, self.model_name, self.cost_meter
                ),
            )
            answer = await self.apply_limit_choice(choice)
            if answer is None:
                self.console.print("Choose Continue, Revert, or Stop.")
                continue
            return answer
        return ""

    def _execute(self, prompt: str) -> Awaitable[str]:
        """Run a turn and print each tool as it finishes."""
        return self.runtime.execute_turn(prompt, **self._live_callbacks())

    def _live_callbacks(self) -> dict[str, Callable[..., None]]:
        return {
            "on_tool_call": self._show_tool_call,
            "on_tool_result": self._show_tool_result,
            "on_step_text": self._show_step_text,
            "on_delta": self._show_delta,
            "on_diff": self._show_diff,
        }

    def _begin_wait(self) -> None:
        """Show that the model is working until the first word or tool arrives."""
        self._end_wait()
        self._activity = self.console.status("[dim]Thinking…[/dim]", spinner="dots")
        self._activity.start()

    def _end_wait(self) -> None:
        """Drop the spinner before printing. A live spinner redraws over the stream."""
        activity = self._activity
        self._activity = None
        if activity is not None:
            activity.stop()

    def _show_delta(self, text: str) -> None:
        """Stream the reply live until a tool runs. After that, show one note row."""
        self._end_wait()
        if self._log.active:
            self._log.add_text(text)
            self._repaint_tail()
            return
        if not self._streamed:
            self.console.print()
        self._streamed += text
        self.console.print(text, end="", markup=False, highlight=False)

    def _show_answer(self, response: str) -> None:
        """Print the reply once, below the summary. Skip it when it already streamed."""
        streamed = self._streamed
        if streamed and (response == streamed or response.endswith(streamed)):
            if self.runtime.turn_warning:
                self.console.print(f"\n[dim]{self.runtime.turn_warning}[/dim]")
            if not streamed.endswith("\n"):
                self.console.print()
            return
        if self._log.actions:
            self.console.print()
            self.console.print(_reply_body(response))
            self.console.print()
            return
        self._print_reply(response)

    def _show_step_text(self, text: str) -> None:
        self._end_wait()
        self.console.print()
        self.console.print(Markdown(text))

    def _toolbar(self) -> list[tuple[str, str]]:
        tokens = toolbar_tokens(self.workspace, self.model_name, self.cost_meter)
        if self._log.actions:
            tokens = [
                *tokens,
                ("class:bottom-toolbar.text", "  ·  ctrl+o to expand"),
            ]
        return tokens

    async def show_activity(self) -> None:
        """The last turn's notes, commands, and output. ctrl+o closes the view."""
        text = self._log.transcript()
        if not text:
            return
        if not self.console.is_terminal:
            self.console.print(text, markup=False, highlight=False)
            return
        await transcript_viewer(text).run_async()

    def _show_tool_call(self, name: str, arguments: dict) -> None:
        self._end_wait()
        if self._streamed:
            if not self._streamed.endswith("\n"):
                self.console.print()
            # Already on screen. The transcript still needs it as a note.
            self._log.add_text(self._streamed)
            self._streamed = ""
        self._log.add_action(name, _tool_summary(arguments))
        self._repaint_tail()

    def _show_output_delta(self, stream: str, text: str) -> None:
        """Keep live output for the transcript. The summary does not show it."""
        _ = stream
        action = self._log.last_action()
        if action is not None:
            action.body += text.replace("\r", "")

    def _show_tool_result(self, call: ToolCall, text: str) -> None:
        action = self._log.last_action()
        if action is not None:
            if call.name == "bash":
                _finish_bash(action, text)
            else:
                action.body = text
        self._repaint_tail()
        self._begin_wait()

    def _show_diff(self, path: str, diff: str) -> None:
        action = self._log.last_action()
        if not diff.strip() or action is None:
            return
        block = f"{path}\n{diff}".strip()
        action.body = f"{action.body}\n{block}".strip() if action.body else block

    def _settle(self) -> None:
        """Leave the final summary above the prompt. Later output prints below it."""
        self._log.flush()
        if self.console.is_terminal:
            self._repaint_tail()
        else:
            for row in self._log.summary_lines(self.console.width):
                self.console.print(row, highlight=False)
        self._log.settle()
        self._tail_lines = 0

    def _repaint_tail(self) -> None:
        """Redraw the summary rows in place.

        Every row is cut to one terminal row and there are only a few, so the
        block stays on screen and the cursor can always move back over it.
        """
        if not self.console.is_terminal:
            return
        self._end_wait()
        with self._paint_lock:
            if self._tail_lines:
                self._erase_lines(self._tail_lines)
                self._tail_lines = 0
            rows = self._log.summary_lines(self.console.width)
            for row in rows:
                self.console.print(row, highlight=False, soft_wrap=True)
            self._tail_lines = len(rows)

    def _erase_lines(self, count: int) -> None:
        if count <= 0 or not self.console.is_terminal:
            return
        self.console.file.write(f"\x1b[{count}A\x1b[J")
        self.console.file.flush()

    def _print_reply(self, response: str) -> None:
        self.console.print()
        self.console.print(
            Panel(
                _reply_body(response),
                title="[bold cyan]PARI Agent[/bold cyan]",
                border_style="dim",
            )
        )
        self.console.print()


def _reply_body(response: str) -> Markdown | Text:
    # Provider detail is literal text. Markdown would restyle underscores.
    if response.startswith("Model error\n"):
        return Text(response)
    return Markdown(response)


def _finish_bash(action: Action, text: str) -> None:
    """Store the exit code and output. A streamed run keeps what it printed."""
    notice, payload = _bash_payload(text)
    if payload is None:
        output = action.body or text
    else:
        raw = payload.get("output")
        output = raw if isinstance(raw, str) else ""
        code = payload.get("exit_code")
        if isinstance(code, int):
            action.exit_code = code
        side = payload.get("sidecar_path")
        if isinstance(side, str) and side:
            output = f"{output}\n{side}".strip()
    if notice:
        output = f"{notice}\n{output}".strip()
    action.body = output


def _bash_payload(text: str) -> tuple[str, dict | None]:
    """Split a daemon notice from the bash result object."""
    notice = ""
    body = text
    if text.startswith("[DAEMON DETECTED]"):
        notice, _, body = text.partition("\n")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return notice, None
    if not isinstance(payload, dict):
        return notice, None
    return notice, payload


def _tool_summary(arguments: dict) -> str:
    """The one argument that tells you which command or path is running."""
    for key in ("command", "path", "query", "pattern"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            one = " ".join(value.split())
            if len(one) > 120:
                return one[:117] + "..."
            return one
    return ""


def _model_refusal(model_name: str, provider: LLMProvider) -> str | None:
    """A cloud model with no credential does not get a turn. The offline model does."""
    if model_name == "pari-core" or isinstance(provider, MockOfflineProvider):
        return None
    if isinstance(provider.api_key, str) and provider.api_key.strip():
        return None
    info = info_for_model(model_name)
    if info is None:
        return f"No provider is implemented for {model_name}."
    return sign_in_hint(info)


def _open_limit_menu() -> None:
    """Open the choice menu with Continue highlighted."""
    get_app().current_buffer.start_completion(select_first=True)


class _LimitValidator(Validator):
    """Keep the menu open until the line is Continue, Revert, or Stop."""

    def validate(self, document: Document) -> None:
        if _limit_action(document.text) is None:
            raise ValidationError(
                message="Choose Continue, Revert, or Stop.",
                cursor_position=len(document.text),
            )


def _limit_action(choice: str) -> str | None:
    word = choice.strip().lower()
    if word.startswith("continue") or word == "c":
        return "continue"
    if word.startswith("revert") or word == "r":
        return "revert"
    if word.startswith("stop") or word == "s":
        return "stop"
    return None


def _revert_message(result: UndoResult) -> str:
    if result.conflicted_files:
        names = ", ".join(result.conflicted_files)
        return f"Could not revert {names}. Those files changed after the edit."
    if result.reverted_files:
        return f"Reverted files: {', '.join(result.reverted_files)}"
    return "Stopped. No file changes to revert."
