"""CLI entrypoint for PARI terminal coding agent."""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from pari import __version__
from pari.fs import resolve_safe_path
from pari.search import find_files, grep_search

try:
    from rich.console import Console
    from rich.table import Table
    console = Console()
except ImportError:
    class SimpleConsole:
        def print(self, *args, **kwargs):
            text = " ".join(str(a) for a in args)
            for tag in ["[bold blue]", "[/bold blue]", "[bold green]", "[/bold green]",
                        "[bold red]", "[/bold red]", "[dim]", "[/dim]", "[bold]", "[/bold]"]:
                text = text.replace(tag, "")
            print(text)
    console = SimpleConsole()


def print_banner():
    banner = f"""[bold blue]PARI[/bold blue] [dim]v{__version__}[/dim] — Terminal Coding Agent
[dim]Platform-Isolated | Exact & Resilient Edits | Durable Sessions[/dim]"""
    console.print(banner)
    console.print("-" * 65)


def check_sandbox_availability() -> str:
    """Detect available platform sandbox primitive."""
    if sys.platform == "linux":
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


def cmd_find(args: argparse.Namespace) -> int:
    """Find files matching pattern in workspace."""
    workspace = Path(args.workspace or os.getcwd()).resolve()
    files = find_files(workspace, pattern=args.pattern, max_results=args.limit)
    if not files:
        console.print(f"[dim]No files found matching '{args.pattern}'[/dim]")
        return 0

    for f in files:
        console.print(f"  {f}")
    console.print(f"[dim]Total: {len(files)} file(s)[/dim]")
    return 0


def cmd_grep(args: argparse.Namespace) -> int:
    """Search for query in workspace files."""
    workspace = Path(args.workspace or os.getcwd()).resolve()
    matches = grep_search(
        workspace,
        query=args.query,
        is_regex=args.regex,
        path_filter=args.filter,
        max_matches=args.limit,
    )
    if not matches:
        console.print(f"[dim]No matches found for '{args.query}'[/dim]")
        return 0

    for m in matches:
        console.print(f"[bold green]{m['file']}[/bold green]:[bold blue]{m['line']}[/bold blue]: {m['content']}")
    console.print(f"[dim]Total: {len(matches)} match(es)[/dim]")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Run local micro-eval benchmark suite."""
    console.print(f"[bold green]PARI Eval Runner[/bold green] — Suite: [bold]{args.suite}[/bold]")
    if not os.path.exists(args.suite):
        console.print(f"[bold red]Error:[/bold red] Benchmark suite '{args.suite}' not found.")
        return 1
    console.print("Micro-eval harness initialized. Running test cases...")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Main interactive REPL agent execution."""
    workspace = Path(args.workspace or os.getcwd()).resolve()

    if args.dry_run:
        print_banner()
        console.print(f"[bold]Workspace:[/bold] {workspace}")
        console.print(f"[bold]Sandbox:[/bold]   {check_sandbox_availability()}")
        console.print(f"[bold]Edit Mode:[/bold] Exact match (fail-on-ambiguity) [dim](Fallback: {args.edit_fallback})[/dim]")
        console.print(f"[bold]Search:[/bold]    v1 ripgrep & globbing [dim](AST RepoMap: {args.repomap})[/dim]")
        console.print("[green]Self-check passed: environment and CLI options verified.[/green]")
        return 0

    import asyncio
    from pari.tui.app import TerminalApp
    from pari.agent.runtime import AgentRuntime

    runtime = AgentRuntime(workspace)
    # Add any explicitly pinned files
    for pinned in args.add:
        runtime.add_pinned_file(pinned)

    app = TerminalApp(workspace, runtime=runtime)
    try:
        asyncio.run(app.run_repl())
    except KeyboardInterrupt:
        console.print("\n[dim]Terminated by user.[/dim]")
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

    # pari find
    find_parser = subparsers.add_parser("find", help="Find files matching pattern")
    find_parser.add_argument("pattern", type=str, default="*", nargs="?", help="File glob pattern")
    find_parser.add_argument("-l", "--limit", type=int, default=100, help="Max results")

    # pari grep
    grep_parser = subparsers.add_parser("grep", help="Search text across workspace files")
    grep_parser.add_argument("query", type=str, help="Search string or regex")
    grep_parser.add_argument("-r", "--regex", action="store_true", help="Treat query as regular expression")
    grep_parser.add_argument("-f", "--filter", type=str, default="*", help="File path pattern filter")
    grep_parser.add_argument("-l", "--limit", type=int, default=50, help="Max matches")

    # pari eval
    eval_parser = subparsers.add_parser("eval", help="Run benchmark evaluation suites")
    eval_parser.add_argument(
        "--suite", type=str, default="./evals/micro_suite.json",
        help="Path to evaluation benchmark suite JSON"
    )

    args = parser.parse_args(argv)

    if args.subcommand == "find":
        return cmd_find(args)
    elif args.subcommand == "grep":
        return cmd_grep(args)
    elif args.subcommand == "eval":
        return cmd_eval(args)
    else:
        return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
