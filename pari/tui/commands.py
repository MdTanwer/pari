"""PARI Layer 9: Interactive Slash Command Dispatcher.

Handles in-session slash commands:
    /undo     - Revert the most recent turn's file modifications
    /diff     - Inspect pending or latest diffs
    /add      - Add a specific file into active context
    /model    - Inspect or switch active LLM model
    /help     - Display available commands
"""

from typing import Callable, Optional, Tuple


class SlashCommandHandler:
    """Dispatches slash commands entered by the developer."""

    def __init__(self):
        pass

    def register(self, command: str, handler: Callable[[str], str]):
        """Register custom slash command handler."""
        raise NotImplementedError

    def handle(self, input_text: str) -> Optional[Tuple[str, str]]:
        """If input_text starts with '/', parse and execute command."""
        raise NotImplementedError
