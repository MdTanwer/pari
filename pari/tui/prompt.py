"""Welcome panel, input prompt, and the status line under it."""

from pathlib import Path

from prompt_toolkit.application.current import get_app
from rich.panel import Panel

from pari.tui.status import CostMeter


def welcome_panel(workspace: Path, model_name: str) -> Panel:
    welcome_text = (
        f"[bold cyan]PARI v0.1.2[/bold cyan] — Coding Agent\n"
        f"[dim]Website   :[/dim] [cyan]https://pari-cli.in[/cyan]\n"
        f"[dim]Workspace :[/dim] [yellow]{workspace}[/yellow]\n"
        f"[dim]Model     :[/dim] [green]{model_name}[/green]\n\n"
        "[dim]Type your message, [/dim][bold cyan]/help[/bold cyan]"
        "[dim] for commands, [/dim][bold cyan]/exit[/bold cyan]"
        "[dim] to quit.[/dim]"
    )
    return Panel(
        welcome_text,
        title="[bold green]PARI[/bold green]",
        border_style="dim cyan",
        padding=(1, 2),
    )


def prompt_tokens() -> list[tuple[str, str]]:
    return [("class:prompt", "> ")]


def placeholder_tokens() -> list[tuple[str, str]]:
    return [("class:placeholder", "Ask PARI to do anything...")]


def toolbar_tokens(
    workspace: Path, model_name: str, cost_meter: CostMeter
) -> list[tuple[str, str]]:
    """Key hints while the completion menu is open, otherwise model and cost."""
    if _completion_open():
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
    status = f"  {model_name} default · {_display_path(workspace)}"
    status += f" · {cost_meter.format_status()}"
    return [("class:bottom-toolbar.text", status)]


def _completion_open() -> bool:
    # get_app raises when this is called outside a running prompt.
    try:
        buff = get_app().current_buffer
    except Exception:
        return False
    if buff.complete_state:
        return True
    text = buff.text.strip()
    return text.startswith("/") and " " not in text


def _display_path(workspace: Path) -> str:
    try:
        return f"~/{workspace.relative_to(Path.home())}"
    except ValueError:
        return str(workspace)
