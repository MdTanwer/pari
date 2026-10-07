from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax


def display_diff(
    diff_text: str, filename: str = "", console: Console | None = None
) -> None:
    """Renders a unified diff in the terminal with colored highlighting."""
    c = console or Console()
    if not diff_text.strip():
        c.print("[dim]No diff changes to display.[/dim]")
        return

    syntax = Syntax(
        diff_text, "diff", theme="monokai", line_numbers=True, word_wrap=True
    )
    if filename:
        title = f"[bold cyan]Diff: {filename}[/bold cyan]"
    else:
        title = "[bold cyan]Unified Diff Preview[/bold cyan]"
    c.print(Panel(syntax, title=title, border_style="cyan", padding=(0, 1)))
