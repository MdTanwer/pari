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
        self._handlers: Dict[str, Callable[[str], str]] = {}

    def register(self, command: str, handler: Callable[[str], str]) -> None:
        """Register custom slash command handler."""
        cmd_name = command.lower().strip()
        if not cmd_name.startswith("/"):
            cmd_name = f"/{cmd_name}"
        self._handlers[cmd_name] = handler

    def handle(self, input_text: str) -> Optional[Tuple[str, str]]:
        """If input_text starts with '/', parse and execute command.

        Returns (command_name, result_message) if handled, or None if not a slash command.
        """
        text = input_text.strip()
        if not text.startswith("/"):
            return None

        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        if cmd in self._handlers:
            output = self._handlers[cmd](args)
            return (cmd, output)

        return (cmd, f"Unknown command: '{cmd}'. Type `/help` for a list of commands.")

