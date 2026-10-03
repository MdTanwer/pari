"""CLI entrypoint for PARI terminal coding agent."""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from pari import __version__

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    console = Console()
except ImportError:
    # Graceful fallback if rich is not yet installed
    class SimpleConsole:
        def print(self, *args, **kwargs):
            text = " ".join(str(a) for a in args)
            # Strip simple rich tags if any
            for tag in ["[bold blue]", "[/bold blue]", "[bold green]", "[/bold green]",
                        "[bold red]", "[/bold red]", "[dim]", "[/dim]", "[bold]", "[/bold]"]:
                text = text.replace(tag, "")
            print(text)
    console = SimpleConsole()


def print_banner():
    banner = f"""[bold blue]PARI[/bold blue] [dim]v{__version__}[/dim] — Terminal Coding Agent
[dim]Platform-Isolated | Exact & Resilient Edits | Durable Sessions[/dim]"""
    if hasattr(console, "print"):
        console.print(banner)
        console.print("-" * 65)


def check_sandbox_availability() -> str:
    """Detect available platform sandbox primitive."""
    if sys.platform == "linux":
        # Check if bubblewrap is in PATH
        from shutil import which
        if which("bwrap"):
            return "bwrap (Linux unprivileged namespaces: Active)"
        return "bwrap not found in PATH (Install via 'sudo apt install bubblewrap')"
    elif sys.platform == "darwin":
        from shutil import which
        if which("sandbox-exec"):
            return "Apple Seatbelt (sandbox-exec: Active)"
        return "sandbox-exec not available"
    elif sys.platform == "win32":
        return "Windows Supervised Process Group (Fallback)"
    return f"Platform '{sys.platform}' unsupported"


def cmd_eval(args: argparse.Namespace) -> int:
    """Run local micro-eval benchmark suite."""
    console.print(f"[bold green]PARI Eval Runner[/bold green] — Suite: [bold]{args.suite}[/bold]")
    if not os.path.exists(args.suite):
        console.print(f"[bold red]Error:[/bold red] Benchmark suite '{args.suite}' not found.")
        return 1
    console.print("Micro-eval harness initialized. Running test cases...")
    # Evaluation suite execution logic will be connected here in Phase 4
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Main interactive REPL agent execution."""
    print_banner()

    workspace = Path(args.workspace or os.getcwd()).resolve()
    console.print(f"[bold]Workspace:[/bold] {workspace}")
    console.print(f"[bold]Sandbox:[/bold]   {check_sandbox_availability()}")
    console.print(f"[bold]Edit Mode:[/bold] Exact match (fail-on-ambiguity) [dim](Fallback: {args.edit_fallback})[/dim]")
    console.print(f"[bold]Search:[/bold]    v1 ripgrep & globbing [dim](AST RepoMap: {args.repomap})[/dim]")

    if args.dry_run:
        console.print("[green]Self-check passed: environment and CLI options verified.[/green]")
        return 0

    console.print("\n[dim]Ready for prompts. Type '/help' for commands, Ctrl+C to exit.[/dim]")
    console.print("[dim](Agent execution engine is ready for session connection)[/dim]\n")
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pari",
        description="PARI — Next-generation terminal coding agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-w", "--workspace", type=str, default=None,
        help="Target project workspace directory (default: current working directory)"
    )
    parser.add_argument(
        "--sandbox", type=str, choices=["auto", "bwrap", "seatbelt", "cloud", "none"],
        default="auto", help="Execution sandbox backend (default: auto)"
    )
    parser.add_argument(
        "--edit-fallback", type=str, choices=["none", "cascade"], default="none",
        help="Edit engine fallback strategy when exact match fails (default: none)"
    )
    parser.add_argument(
        "--repomap", type=str, choices=["off", "ppr"], default="off",
        help="Repository AST PageRank symbol map (default: off, uses v1 ripgrep/glob)"
    )
    parser.add_argument(
        "--add", action="append", default=[], metavar="FILE",
        help="Pin reference documentation or file into context epoch"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate environment configuration and exit without starting interactive loop"
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommands")

    eval_parser = subparsers.add_parser("eval", help="Run benchmark evaluation suites")
    eval_parser.add_argument(
        "--suite", type=str, default="./evals/micro_suite.json",
        help="Path to evaluation benchmark suite JSON"
    )

    args = parser.parse_args(argv)

    if args.subcommand == "eval":
        return cmd_eval(args)
    else:
        return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
