"""PARI Layer 9: Terminal Interface & Differential TUI.

Architectural Purpose:
    Harvested from Pi's differential TUI rendering and Aider's prompt_toolkit interface.
    Closes Cursor F4 (background CPU pegging vector indexer).
    Provides responsive streaming, syntax-highlighted diff review, token cost meter,
    and inline slash commands without heavy Electron overhead.

Subsystems:
    - app: Interactive terminal session loop
    - diff_view: Syntax-highlighted unified diff preview & approval prompt
    - status: Token tracker & USD cost meter
    - commands: Interactive slash commands (/undo, /diff, /model, /help)
"""

from pari.tui.diff_view import display_diff
from pari.tui.status import CostMeter
from pari.tui.commands import SlashCommandHandler

__all__ = [
    "display_diff",
    "CostMeter",
    "SlashCommandHandler",
]
