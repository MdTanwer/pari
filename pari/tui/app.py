"""PARI Layer 9: Interactive Terminal Application & REPL.

Orchestrates prompt_toolkit command-line inputs, Rich differential rendering,
live tool execution feedback, unified diff inspection, and slash commands.
"""

import asyncio
import os
from pathlib import Path
import subprocess
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from pari.agent.runtime import AgentRuntime
from pari.tui.status import CostMeter
from pari.tui.commands import SlashCommandHandler
from pari.tui.diff_view import display_diff


class TerminalApp:
    """Manages developer interactions in the terminal REPL."""

    def __init__(self, workspace: Path, runtime: Optional[AgentRuntime] = None):
        self.workspace = workspace.resolve()
        self.console = Console()
        self.runtime = runtime or AgentRuntime(self.workspace)
        self.cost_meter = CostMeter(self.runtime.provider.model_name)
        self.commands = SlashCommandHandler()
        self._register_slash_commands()

    def _register_slash_commands(self):
        # Register /undo
        def handle_undo(arg: str) -> str:
            res = self.runtime.undo_manager.undo()
            out = []
            if res.reverted_files:
                out.append(f"[bold green]Reverted files:[/bold green] {', '.join(res.reverted_files)}")
            if res.conflicted_files:
                out.append(f"[bold red]Conflicted (manual changes detected, skipped):[/bold red] {', '.join(res.conflicted_files)}")
            if res.disclosed_side_effects:
                out.append(f"[bold yellow]External side effects logged (not reverted):[/bold yellow] {', '.join(res.disclosed_side_effects)}")
            if not res.reverted_files and not res.conflicted_files:
                out.append("[dim]No file changes in current turn to undo.[/dim]")
            return "\n".join(out)

        # Register /diff
        def handle_diff(arg: str) -> str:
            try:
                proc = subprocess.run(
                    ["git", "diff", "--stat"],
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                )
                if proc.stdout.strip():
                    return f"[bold]Git Uncommitted Changes:[/bold]\n{proc.stdout}"
                return "[dim]Working tree clean; no uncommitted git changes.[/dim]"
            except Exception as e:
                return f"[dim]Git not initialized in workspace: {e}[/dim]"

        # Register /add
        def handle_add(arg: str) -> str:
            if not arg.strip():
                return "[red]Usage: /add <file_path>[/red]"
            ok = self.runtime.add_pinned_file(arg.strip())
            if ok:
                return f"[bold green]Added '{arg.strip()}' to active context.[/bold green]"
            return f"[bold red]Could not find or resolve file '{arg.strip()}'.[/bold red]"

        # Register /model
        def handle_model(arg: str) -> str:
            if not arg.strip():
                return f"Active model: [bold cyan]{self.runtime.provider.model_name}[/bold cyan]"
            # Reconfigure provider
            from pari.providers import get_provider
            self.runtime.provider = get_provider(arg.strip())
            self.cost_meter = CostMeter(self.runtime.provider.model_name)
            return f"Switched model to [bold cyan]{self.runtime.provider.model_name}[/bold cyan]"

        self.commands.register("/undo", handle_undo)
        self.commands.register("/diff", handle_diff)
        self.commands.register("/add", handle_add)
        self.commands.register("/model", handle_model)

    def print_welcome(self):
        banner = (
            "[bold cyan]PARI[/bold cyan] — Resilient, Sandbox-First Terminal Coding Agent\n"
            f"[dim]Workspace: {self.workspace}[/dim]\n"
            f"[dim]Model:     {self.runtime.provider.model_name}[/dim]\n"
            "[dim]Type /help for slash commands, or type your request below.[/dim]"
        )
        self.console.print(Panel(banner, border_style="cyan"))

    def on_tool_call(self, name: str, args: dict):
        preview = str(args)[:80] + ("..." if len(str(args)) > 80 else "")
        self.console.print(f"  [bold blue]Tool Call:[/bold blue] [cyan]{name}[/cyan]({preview})")

    def on_diff(self, path: str, diff_text: str):
        display_diff(diff_text, filename=path, console=self.console)

    async def run_repl(self):
        """Main interactive terminal read-eval-print loop."""
        self.print_welcome()
        self.runtime.start_session()

        # Try using prompt_toolkit for full history and line editing
        try:
            from prompt_toolkit import PromptSession
            session = PromptSession()
            get_input = session.prompt_async
        except ImportError:
            async def get_input(prompt_str: str) -> str:
                return input(prompt_str)

        while True:
            try:
                user_input = await get_input("pari > ")
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[dim]Session ended.[/dim]")
                break

            stripped = user_input.strip()
            if not stripped:
                continue

            if stripped in ("/exit", "/quit"):
                self.console.print("[dim]Exiting PARI. Goodbye![/dim]")
                break

            # Handle slash commands
            cmd_result = self.commands.handle(stripped)
            if cmd_result:
                cmd_name, output = cmd_result
                self.console.print(output)
                continue

            # Execute turn via agent runtime
            try:
                response = await self.runtime.execute_turn(
                    stripped,
                    on_tool_call=self.on_tool_call,
                    on_diff=self.on_diff,
                )
                self.console.print(Markdown(response))
                self.console.print(self.cost_meter.format_status(), style="dim green")
            except Exception as e:
                self.console.print(f"[bold red]Turn Execution Error:[/bold red] {e}")
