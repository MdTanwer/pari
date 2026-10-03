"""PARI Layer 9: Unified Diff Preview & Confirmation.

Architectural Purpose:
    Displays syntax-highlighted unified diffs directly in the terminal before
    mutations are written to disk, preventing accidental destructive edits.
"""

from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel


def display_diff(diff_text: str, filename: str = "", console: Console = None) -> None:
    """Renders a unified diff in the terminal with colored highlighting."""
    if not diff_text.strip():
        return

    c = console or Console()
    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
    title = f"Proposed Diff: {filename}" if filename else "Proposed Changes"
    c.print(Panel(syntax, title=title, border_style="cyan"))
