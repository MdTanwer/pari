"""PARI Layer 9: Terminal Interface & Differential TUI.

Architectural Purpose:
    Harvested from Pi's differential TUI rendering and Aider's prompt_toolkit interface.
    Closes Cursor F4 (background CPU pegging vector indexer).
    Provides responsive streaming, syntax-highlighted diff review, token cost meter,
    and inline slash commands without heavy Electron overhead.

Subsystems:
    - app: Interactive terminal session loop
    - slash: Built-in slash commands
    - completer: Slash-command suggestions
    - keys: Completion-menu key bindings
    - prompt: Welcome panel and status line
    - style: Prompt and menu colors
    - diff_view: Syntax-highlighted unified diff preview
    - status: Token tracker and USD cost meter
    - commands: Slash-command dispatcher
"""

from pari.tui.app import TerminalApp
from pari.tui.commands import SlashCommandHandler
from pari.tui.diff_view import display_diff
from pari.tui.status import CostMeter, TokenUsage


__all__ = [
    "TerminalApp",
    "SlashCommandHandler",
    "display_diff",
    "CostMeter",
    "TokenUsage",
]
