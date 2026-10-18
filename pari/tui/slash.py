"""Slash commands that answer inside the session and do not call the model.

``/login`` and ``/logout`` are not here. Those menus take over the terminal,
so the REPL loop runs them before this dispatcher.
"""

from pathlib import Path
from typing import Protocol

from rich.console import Console

from pari.agent.loop import workspace_diff
from pari.agent.runtime import AgentRuntime
from pari.auth.login import sign_out, status_text
from pari.tui.commands import SlashCommandHandler
from pari.tui.diff_view import display_diff
from pari.tui.status import CostMeter


class CommandHost(Protocol):
    """The session fields a slash command is allowed to change."""

    workspace: Path
    model_name: str
    runtime: AgentRuntime
    console: Console
    cost_meter: CostMeter


class SessionCommands:
    """Register the built-in commands and run the one that matches the line."""

    def __init__(self, host: CommandHost):
        self.host = host
        self.handler = SlashCommandHandler()
        self.handler.register("/help", self._help)
        self.handler.register("/diff", self._diff)
        self.handler.register("/undo", self._undo)
        self.handler.register("/model", self._model)
        self.handler.register("/add", self._add)
        self.handler.register("/snapshot", self._snapshot)
        self.handler.register("/cost", self._cost)
        self.handler.register("/reset", self._reset)
        self.handler.register("/resume", self._resume)
        self.handler.register("/login", self._login)
        self.handler.register("/logout", self._logout)

    def handle(self, text: str) -> tuple[str, str] | None:
        """Return ``(command, message)`` when the line is a slash command."""
        return self.handler.handle(text)

    def _help(self, _args: str) -> str:
        return (
            "**Available Slash Commands:**\n\n"
            "- `/diff` - Preview pending or latest unified diffs\n"
            "- `/undo` - Revert the most recent file change\n"
            "- `/model [name]` - Inspect or switch active LLM\n"
            "- `/add [path]` - Pin reference file or glob into context\n"
            "- `/snapshot [name]` - Save a named restore point\n"
            "- `/cost` - Show token and cost totals\n"
            "- `/reset` - Clear the conversation\n"
            "- `/resume [id]` - List previous sessions or resume one\n"
            "- `/login` - Sign in with an account or an API key\n"
            "- `/logout` - Remove a saved sign-in\n"
            "- `/clear` - Clear terminal screen\n"
            "- `/help` - Show this commands overview\n"
            "- `/exit` or `/quit` - End interactive session"
        )

    def _diff(self, _args: str) -> str:
        diff = workspace_diff(self.host.workspace)
        if not diff.strip():
            return "No uncommitted diff."
        display_diff(diff, filename=str(self.host.workspace), console=self.host.console)
        return diff

    def _undo(self, _args: str) -> str:
        res = self.host.runtime.undo_manager.undo()
        if res.reverted_files:
            return f"Reverted files: {', '.join(res.reverted_files)}"
        return "No previous file modifications in session history to undo."

    def _model(self, args: str) -> str:
        if args:
            name = args.strip()
            try:
                self.host.runtime.set_model(name)
            except (RuntimeError, NotImplementedError) as exc:
                return str(exc)
            self.host.model_name = self.host.runtime.model_name
            self.host.cost_meter.model_family = self.host.model_name.lower()
            return f"Switched active model to: `{self.host.model_name}`"
        tiers = "openai, deepseek, anthropic, grok, openrouter, pari-core"
        return f"Active model: `{self.host.model_name}` (Tiers: {tiers})"

    def _login(self, _args: str) -> str:
        return status_text()

    def _logout(self, args: str) -> str:
        provider = args.strip()
        if not provider:
            return "Run `/logout` to choose a saved sign-in."
        try:
            return sign_out(provider)
        except (ValueError, RuntimeError) as exc:
            return str(exc)

    def _snapshot(self, args: str) -> str:
        label = self.host.runtime.save_snapshot(args)
        return f"Saved snapshot `{label}`."

    def _cost(self, _args: str) -> str:
        return self.host.cost_meter.format_breakdown()

    def _reset(self, _args: str) -> str:
        session_id = self.host.runtime.reset_conversation()
        return f"Conversation cleared. Session `{session_id}`."

    def _resume(self, args: str) -> str:
        choice = args.strip()
        if choice:
            try:
                session_id = self.host.runtime.resume(choice)
            except FileNotFoundError as exc:
                return str(exc)
            return f"Resumed session `{session_id}`."
        rows = self.host.runtime.list_sessions()
        if not rows:
            return "No previous sessions."
        lines = ["**Previous sessions:**"]
        for session_id, prompt in rows:
            title = prompt or "(no messages yet)"
            lines.append(f"- `{session_id}` — {title}")
        lines.append("Resume one with `/resume <id>`.")
        return "\n".join(lines)

    def _add(self, args: str) -> str:
        if not args:
            return "Usage: `/add <file_or_glob>` (e.g. `/add pyproject.toml`)"
        added = self.host.runtime.add_pinned_file(args.strip())
        if added:
            return f"Added {args.strip()} to active context."
        target = (self.host.workspace / args.strip()).resolve()
        if not target.is_file():
            return f"File not found: `{args}`"
        return f"File is outside the workspace: `{args}`"
