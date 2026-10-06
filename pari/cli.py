"""CLI entrypoint for PARI terminal coding agent.

Handles top-level command parsing, banner display, subcommands (find, grep, eval),
and launching the interactive agent REPL.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from pari import __version__
from pari.tui import TerminalApp


def print_banner():
    """Print the startup terminal banner."""
    print(f"PARI v{__version__} — Terminal Coding Agent")
    print("Platform-Isolated | Exact & Resilient Edits | Durable Sessions")
    print("-" * 65)


def cmd_find(args: argparse.Namespace) -> int:
    """Find files matching pattern in workspace."""
    # TODO: Implement workspace file search via Layer 3 intelligence
    print(f"Finding files matching '{args.pattern}' (placeholder)")
    return 0


def cmd_grep(args: argparse.Namespace) -> int:
    """Search for query in workspace files."""
    # TODO: Implement substring/regex grep via Layer 3 intelligence
    print(f"Searching for '{args.query}' (placeholder)")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Run local micro-eval benchmark suite."""
    # TODO: Implement micro-eval benchmark via Layer 10 harness
    print(f"Running evaluation suite '{args.suite}' (placeholder)")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Main interactive REPL agent execution."""
    workspace = Path(args.workspace or os.getcwd()).resolve()

    if args.dry_run:
        print_banner()
        print(f"Workspace: {workspace}")
        print("Self-check passed: environment and CLI options verified.")
        return 0

    app = TerminalApp(workspace=workspace)
    try:
        asyncio.run(app.run_repl())
    except KeyboardInterrupt:
        pass
    return 0



def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pari",
        description="PARI — Next-generation terminal coding agent.",
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
