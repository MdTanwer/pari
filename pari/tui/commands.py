"""PARI Layer 9: Interactive Slash Command Dispatcher.

Handles in-session slash commands:
    /undo     - Revert the most recent turn's file modifications
    /diff     - Inspect pending or latest diffs
    /add      - Add a specific file into active context
    /model    - Inspect or switch active LLM model
    /help     - Display available commands
"""

from typing import Callable, Dict, Optional, Tuple


class SlashCommandHandler:
    """Dispatches slash commands entered by the developer."""

    def __init__(self):
        self.handlers: Dict[str, Callable[[str], str]] = {}
        self._register_builtins()

    def _register_builtins(self):
        self.handlers["/help"] = lambda arg: (
            "Available Slash Commands:\n"
            "  /undo       Revert the most recent turn's file changes\n"
            "  /diff       Show git status and pending unified diffs\n"
            "  /add <file> Inject target file into active context\n"
            "  /model <m>  Switch active LLM model\n"
            "  /exit       End the current session"
        )

    def register(self, command: str, handler: Callable[[str], str]):
        self.handlers[command] = handler

    def handle(self, input_text: str) -> Optional[Tuple[str, str]]:
        """If input_text starts with '/', parse and execute command. Returns (cmd, result)."""
        stripped = input_text.strip()
        if not stripped.startswith("/"):
            return None

        parts = stripped.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in self.handlers:
            return cmd, self.handlers[cmd](arg)
        return cmd, f"Unknown command '{cmd}'. Type /help for available commands."
