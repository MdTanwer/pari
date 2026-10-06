import asyncio
from pathlib import Path
import shutil
from typing import Optional

from collections.abc import Iterable
from prompt_toolkit import PromptSession
from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_completions
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from pari.tui.commands import SlashCommandHandler
from pari.tui.diff_view import display_diff

# Slash command metadata definitions
COMMAND_METADATA = [
    ("/help", "Show available slash commands and help"),
    ("/diff", "Preview pending or latest unified diffs"),
    ("/undo", "Revert the most recent file change"),
    ("/clear", "Clear terminal screen"),
    ("/model", "Inspect or switch active LLM"),
    ("/add", "Pin reference file or glob into context"),
    ("/exit", "End interactive session"),
    ("/quit", "End interactive session"),
]


class SlashCommandCompleter(Completer):
    """Autocompleter for slash commands with formatted descriptions and clean prefix matching."""

    def __init__(self, commands: list[tuple[str, str]] | None = None):
        self.commands = commands or COMMAND_METADATA

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        text = document.text_before_cursor.lstrip()

        # If user has entered arguments (e.g. "/model gpt-4o "), don't complete slash commands
        if " " in text:
            return

        # Trigger on '/' or when explicit completion is requested (e.g. Tab on empty line)
        if not text.startswith("/") and not (complete_event.completion_requested and not text):
            return

        query = text.lower()
        for cmd, desc in self.commands:
            if cmd.lower().startswith(query):
                yield Completion(
                    text=cmd,
                    start_position=-len(text),
                    display=cmd,
                    display_meta=desc,
                )


# Modern CLI theme matching the completion dropdown menu & toolbar styling
CLI_STYLE = Style.from_dict({
    # Prompt & input
    "prompt": "fg:#38bdf8 bold",
    "": "fg:#f3f4f6",
    "placeholder": "fg:#6b7280 italic",

    # Completion Menu dropdown
    "completion-menu": "bg:#18181b fg:#f4f4f5",
    "completion-menu.completion": "bg:#18181b fg:#38bdf8",
    "completion-menu.completion.current": "bg:#27272a fg:#38bdf8 bold",
    "completion-menu.meta.completion": "bg:#18181b fg:#717882",
    "completion-menu.meta.completion.current": "bg:#27272a fg:#e4e4e7",
    "completion-menu.multi-column-meta": "bg:#18181b fg:#717882",

    # Scrollbar
    "scrollbar.background": "bg:#18181b",
    "scrollbar.button": "bg:#3f3f46",
    "scrollbar.arrow": "bg:#18181b fg:#717882",

    # Bottom toolbar & navigation hint keys
    "bottom-toolbar": "bg:default fg:#717882",
    "bottom-toolbar.text": "bg:default fg:#717882",
    "toolbar-key": "fg:#38bdf8 bold",
    "toolbar-key-esc": "fg:#717882",
    "toolbar-action": "fg:#717882",
    "toolbar-dot": "fg:#4b5563",
})


class TerminalApp:
    """Manages developer interactions in the terminal REPL."""

    def __init__(self, workspace: Path, model_name: str = "pari-core"):
        self.workspace = workspace.resolve()
        self.model_name = model_name
        self.console = Console()
        # TODO:
        # self.runtime = runtime or AgentRuntime(self.workspace)
        # self.cost_meter = CostMeter(model_family=self.model_name)  # later todo
        self.commands = SlashCommandHandler()
        self._register_commands()

        self.completer = SlashCommandCompleter()
        self.key_bindings = self._create_key_bindings()
        self.session: PromptSession = PromptSession(
            history=InMemoryHistory(),
            completer=self.completer,
            style=CLI_STYLE,
            complete_while_typing=True,
            complete_style=CompleteStyle.COLUMN,
            reserve_space_for_menu=10,
            key_bindings=self.key_bindings,
        )

    def _create_key_bindings(self) -> KeyBindings:
        """Keybindings for autocomplete navigation: enter select, tab complete, esc cancel."""
        kb = KeyBindings()

        @kb.add("enter", filter=has_completions)
        def _handle_enter(event):
            buff = event.current_buffer
            if buff.complete_state and buff.complete_state.current_completion:
                buff.apply_completion(buff.complete_state.current_completion)
            else:
                buff.validate_and_handle()

        @kb.add("tab", filter=has_completions)
        def _handle_tab(event):
            buff = event.current_buffer
            if buff.complete_state:
                buff.complete_next()

        @kb.add("s-tab", filter=has_completions)
        def _handle_s_tab(event):
            buff = event.current_buffer
            if buff.complete_state:
                buff.complete_previous()

        @kb.add("down", filter=has_completions)
        def _handle_down(event):
            event.current_buffer.complete_next()

        @kb.add("up", filter=has_completions)
        def _handle_up(event):
            event.current_buffer.complete_previous()

        @kb.add("escape", filter=has_completions)
        def _handle_escape(event):
            buff = event.current_buffer
            buff.cancel_completion()

        return kb

    def _register_commands(self) -> None:
        """Register built-in slash commands."""
        self.commands.register("/help", self._cmd_help)
        self.commands.register("/diff", self._cmd_diff)
        self.commands.register("/undo", self._cmd_undo)
        self.commands.register("/model", self._cmd_model)
        self.commands.register("/add", self._cmd_add)

    def _cmd_help(self, args: str) -> str:
        return (
            "**Available Slash Commands:**\n\n"
            "- `/diff` - Preview pending or latest unified diffs\n"
            "- `/undo` - Revert the most recent file change\n"
            "- `/model [name]` - Inspect or switch active LLM\n"
            "- `/add [path]` - Pin reference file or glob into context\n"
            "- `/clear` - Clear terminal screen\n"
            "- `/help` - Show this commands overview\n"
            "- `/exit` or `/quit` - End interactive session"
        )

    def _cmd_diff(self, args: str) -> str:
        # Display sample/active unified diff preview
        sample_diff = (
            "--- a/src/example.py\n"
            "+++ b/src/example.py\n"
            "@@ -1,3 +1,3 @@\n"
            "-def hello():\n"
            "-    return 'world'\n"
            "+def hello() -> str:\n"
            "+    return 'hello world from PARI!'"
        )
        display_diff(sample_diff, filename="src/example.py", console=self.console)
        return "Inspecting diff preview for `src/example.py`."

    def _cmd_undo(self, args: str) -> str:
        # TODO: res = self.runtime.undo_manager.undo()
        if hasattr(self, "runtime") and hasattr(self.runtime, "undo_manager"):
            res = self.runtime.undo_manager.undo()
            if res.reverted_files:
                return f"Reverted files: {', '.join(res.reverted_files)}"
        return "No previous file modifications in session history to undo."

    def _cmd_model(self, args: str) -> str:
        if args:
            self.model_name = args.strip()
            # TODO: self.cost_meter.model_family = self.model_name.lower()
            if hasattr(self, "cost_meter"):
                self.cost_meter.model_family = self.model_name.lower()
            return f"Switched active model to: `{self.model_name}`"
        return f"Active model: `{self.model_name}` (Tiers: claude-3-7-sonnet, claude-3-5-sonnet, gpt-4o, pari-core)"

    def _cmd_add(self, args: str) -> str:
        if not args:
            return "Usage: `/add <file_or_glob>` (e.g. `/add pyproject.toml`)"
        # TODO: self.runtime.add_pinned_file(args.strip())
        if hasattr(self, "runtime"):
            added = self.runtime.add_pinned_file(args.strip())
            if added:
                return f"Added {args.strip()} to active context."
        target = (self.workspace / args.strip()).resolve()
        if not target.exists():
            return f"File not found: `{args}`"
        try:
            rel = target.relative_to(self.workspace)
        except ValueError:
            rel = target
        return f"Added {rel} to active context."



    def print_welcome(self):
        """Display startup banner."""
        welcome_text = (
            f"[bold cyan]PARI v0.1.1[/bold cyan] — Coding Agent\n"
            f"[dim]Website   :[/dim] [cyan]https://pari-cli.in[/cyan]\n"
            f"[dim]Workspace :[/dim] [yellow]{self.workspace}[/yellow]\n"
            f"[dim]Model     :[/dim] [green]{self.model_name}[/green]\n\n"
            f"[dim]Type your message, [/dim][bold cyan]/help[/bold cyan][dim] for commands, [/dim][bold cyan]/exit[/bold cyan][dim] to quit.[/dim]"
        )
        self.console.print(
            Panel(
                welcome_text,
                title="[bold green]PARI[/bold green]",
                border_style="dim cyan",
                padding=(1, 2),
            )
        )

    def get_prompt(self):
        """Clean prompt indicator matching modern CLI design."""
        return [
            ("class:prompt", "> "),
        ]

    def get_placeholder(self):
        """Placeholder text when input line is empty."""
        return [("class:placeholder", "Ask PARI to do anything...")]

    def get_bottom_toolbar(self):
        """Dynamic toolbar showing key navigation hints during completion or session status."""
        try:
            app = get_app()
            buff = app.current_buffer
            is_completing = bool(buff.complete_state) or (
                buff.text.strip().startswith("/") and " " not in buff.text.strip()
            )
        except Exception:
            is_completing = False

        if is_completing:
            return [
                ("class:toolbar-key", "↑/↓"),
                ("class:toolbar-action", " Navigate "),
                ("class:toolbar-dot", "· "),
                ("class:toolbar-key", "enter"),
                ("class:toolbar-action", " Select "),
                ("class:toolbar-dot", "· "),
                ("class:toolbar-key", "tab"),
                ("class:toolbar-action", " Complete\n"),
                ("class:toolbar-key-esc", "esc"),
                ("class:toolbar-action", " to cancel"),
            ]

        home = Path.home()
        try:
            rel_path = f"~/{self.workspace.relative_to(home)}"
        except ValueError:
            rel_path = str(self.workspace)

        cost_str = f" · {self.cost_meter.format_status()}" if hasattr(self, "cost_meter") else ""
        status_meta = f"  {self.model_name} default · {rel_path}{cost_str}"
        return [
            ("class:bottom-toolbar.text", status_meta),
        ]

    def process_message(self, user_msg: str) -> str:
        """Process user message and generate a response."""
        # 1. Check slash commands first
        cmd_result = self.commands.handle(user_msg)
        if cmd_result is not None:
            _, output = cmd_result
            return output

        normalized = user_msg.strip().lower()

        # 2. Handle greetings like "hi how are you", "hi howr you", etc.
        if "how" in normalized and ("are you" in normalized or "r you" in normalized or "howr" in normalized):
            return "Good! How can I help you today?"
        elif normalized in ("hi", "hello", "hey"):
            return "Hello! How can I assist you with your project?"

        # 3. Normal turn execution (TODO: self.cost_meter.add_usage)
        if hasattr(self, "cost_meter"):
            self.cost_meter.add_usage(in_tokens=len(user_msg.split()) * 4 + 150, out_tokens=60)
        return f"Received: {user_msg}\n\n*(Agent core is ready for prompt orchestration)*"


    async def run_repl(self):
        """Main interactive terminal read-eval-print loop."""
        self.print_welcome()

        while True:
            try:
                user_input = await self.session.prompt_async(
                    message=self.get_prompt,
                    placeholder=self.get_placeholder,
                    bottom_toolbar=self.get_bottom_toolbar,
                )

                text = user_input.strip()
                if not text:
                    continue

                # 2. Built-in session commands
                if text in ("/exit", "/quit", "exit", "quit"):
                    self.console.print("[dim]Exiting PARI session. Goodbye![/dim]")
                    break

                if text == "/clear":
                    self.console.clear()
                    self.print_welcome()
                    continue

                # 3. Simulate thinking with Rich status spinner
                with self.console.status("[bold cyan]PARI is thinking...", spinner="dots"):
                    await asyncio.sleep(0.4)
                    response = self.process_message(text)

                # 4. Render response via Rich
                self.console.print()
                self.console.print(Panel(Markdown(response), title="[bold cyan]PARI Agent[/bold cyan]", border_style="dim"))
                self.console.print()

            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[dim]Session interrupted. Goodbye![/dim]")
                break
