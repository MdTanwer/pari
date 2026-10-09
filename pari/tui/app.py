"""REPL loop.

Slash commands, the completion menu, key bindings, and the prompt chrome live
in the neighbouring modules. This file owns the session and decides whether a
line is a local command or a model turn.
"""

import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import CompleteStyle
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from pari.agent.runtime import AgentRuntime
from pari.auth.interactive import login_tty, logout_tty
from pari.auth.login import sign_in_hint
from pari.auth.providers import info_for_model
from pari.providers.base import LLMProvider
from pari.providers.mock import MockOfflineProvider
from pari.session.undo import UndoResult
from pari.tui.completer import SlashCommandCompleter
from pari.tui.keys import create_key_bindings
from pari.tui.prompt import (
    placeholder_tokens,
    prompt_tokens,
    toolbar_tokens,
    welcome_panel,
)
from pari.tui.slash import SessionCommands
from pari.tui.status import CostMeter
from pari.tui.style import CLI_STYLE


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
        self.session: PromptSession = PromptSession(
            history=InMemoryHistory(),
            completer=SlashCommandCompleter(),
            style=CLI_STYLE,
            complete_while_typing=True,
            complete_style=CompleteStyle.COLUMN,
            reserve_space_for_menu=10,
            key_bindings=create_key_bindings(),
        )

    def print_welcome(self) -> None:
        self.console.print(welcome_panel(self.workspace, self.model_name))

    def process_message(self, user_msg: str) -> str | None:
        """Return a local answer, or None when the line should run a model turn."""
        quick = self.commands.handle(user_msg)
        if quick is not None:
            return quick[1]
        return _greeting(user_msg)

    async def respond(self, user_msg: str) -> str:
        """Answer a slash command locally, or run one agent turn."""
        quick = self.process_message(user_msg)
        if quick is not None:
            return quick
        blocked = _model_refusal(self.model_name, self.runtime.provider)
        if blocked is not None:
            return blocked
        text = await self.runtime.execute_turn(user_msg)
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
        while True:
            try:
                user_input = await self.session.prompt_async(
                    message=prompt_tokens,
                    placeholder=placeholder_tokens,
                    bottom_toolbar=lambda: toolbar_tokens(
                        self.workspace, self.model_name, self.cost_meter
                    ),
                )
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
        status = "[bold cyan]PARI is thinking..."
        with self.console.status(status, spinner="dots"):
            response = await self.respond(text)
        self._print_reply(response)
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
            text = await self.runtime.continue_turn()
            self.cost_meter.add_usage(
                self.runtime.tokens_in,
                self.runtime.tokens_out,
                self.runtime.cached_tokens,
            )
            if self.runtime.turn_warning:
                return f"{self.runtime.turn_warning}\n\n{text}"
            return text
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
            choice = await self.session.prompt_async(
                "Continue (+10 turns), Revert, or Stop? "
            )
            answer = await self.apply_limit_choice(choice)
            if answer is None:
                self.console.print("Choose Continue, Revert, or Stop.")
                continue
            return answer
        return ""

    def _print_reply(self, response: str) -> None:
        self.console.print()
        self.console.print(
            Panel(
                Markdown(response),
                title="[bold cyan]PARI Agent[/bold cyan]",
                border_style="dim",
            )
        )
        self.console.print()


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


def _greeting(user_msg: str) -> str | None:
    normalized = user_msg.strip().lower()
    greeting = "are you" in normalized or "r you" in normalized or "howr" in normalized
    if "how" in normalized and greeting:
        return "Good! How can I help you today?"
    if normalized in ("hi", "hello", "hey"):
        return "Hello! How can I assist you with your project?"
    return None
