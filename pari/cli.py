"""CLI entrypoint for PARI terminal coding agent.

Handles top-level command parsing, banner display, subcommands (find, grep, eval),
and launching the interactive agent REPL.
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

from pari import __version__
from pari.auth.interactive import login_tty, logout_tty
from pari.auth.login import (
    NO_MODEL,
    default_model_name,
    sign_in,
    sign_in_hint,
    sign_out,
    status_text,
)
from pari.auth.providers import PROVIDERS, get_info
from pari.auth.verify import verify_api_key
from pari.intelligence.search import find_files, grep_search
from pari.providers import get_provider
from pari.sandbox.dispatcher import get_sandbox_runner
from pari.tui import TerminalApp


def print_banner():
    """Print the startup terminal banner."""
    print(f"PARI v{__version__} — Terminal Coding Agent (https://pari-cli.in)")
    print("Platform-Isolated | Exact & Resilient Edits | Durable Sessions")
    print("-" * 65)


def cmd_find(args: argparse.Namespace) -> int:
    """Find files matching pattern in workspace."""
    workspace = _workspace(args)
    pattern = args.pattern or "*"
    matches = find_files(workspace, pattern, args.limit)
    if not matches:
        print(f"No files matched '{pattern}'.", file=sys.stderr)
        return 1
    print("\n".join(matches))
    return 0


def cmd_grep(args: argparse.Namespace) -> int:
    """Search for query in workspace files."""
    workspace = _workspace(args)
    try:
        matches = grep_search(
            workspace,
            args.query,
            is_regex=args.regex,
            path_filter=args.filter,
            max_matches=args.limit,
        )
    except re.error as exc:
        print(f"Invalid regular expression: {exc}", file=sys.stderr)
        return 2
    if not matches:
        print(f"No matches for '{args.query}'.", file=sys.stderr)
        return 1
    for hit in matches:
        print(f"{hit['file']}:{hit['line']}:{hit['content']}")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    """Open the sign-in menus, or save one credential from flags."""
    if args.api_key or args.account:
        if not args.provider or bool(args.api_key) == bool(args.account):
            print(
                "Choose one: --api-key <key> or --account <token>.",
                file=sys.stderr,
            )
            return 1
        method = "api_key" if args.api_key else "account"
        secret = args.api_key or args.account or ""
        try:
            print(sign_in(args.provider, secret, method, verify=verify_api_key))
        except (ValueError, RuntimeError) as exc:
            print(exc, file=sys.stderr)
            return 1
        return 0
    if sys.stdin.isatty() and sys.stdout.isatty():
        return login_tty(args.provider)
    if args.provider:
        print(sign_in_hint(get_info(args.provider)), file=sys.stderr)
        return 1
    print(status_text())
    print("pari-cli login")
    print("pari-cli login <provider> --api-key <key>")
    print("pari-cli login <provider> --account <token>")
    return 0


def cmd_logout(args: argparse.Namespace) -> int:
    """Remove one saved sign-in, or open the picker when no provider is named."""
    if not args.provider:
        return logout_tty()
    try:
        print(sign_out(args.provider))
    except (ValueError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Refuse a suite run until the evaluation harness exists."""
    suite = Path(args.suite)
    if not suite.is_file():
        print(f"Evaluation suite not found: {suite}", file=sys.stderr)
        return 1
    print(
        "The evaluation harness is not available yet.",
        file=sys.stderr,
    )
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Main interactive REPL agent execution."""
    workspace = _workspace(args)
    pinned = _pin_error(workspace, args.add)
    if pinned is not None:
        print(pinned, file=sys.stderr)
        return 1
    try:
        model = args.model or default_model_name()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1
    if not model:
        print(NO_MODEL, file=sys.stderr)
        return 1
    if args.dry_run:
        return _dry_run(workspace, model, args.sandbox)

    try:
        app = TerminalApp(
            workspace=workspace,
            model_name=model,
            edit_fallback=args.edit_fallback,
            repomap=args.repomap,
            sandbox_mode=args.sandbox,
        )
    except (RuntimeError, NotImplementedError, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        return 1
    for rel in args.add:
        app.runtime.add_pinned_file(rel)
    try:
        asyncio.run(app.run_repl())
    except KeyboardInterrupt:
        pass
    return 0


def _workspace(args: argparse.Namespace) -> Path:
    return Path(args.workspace or os.getcwd()).resolve()


def _pin_error(workspace: Path, paths: list[str]) -> str | None:
    for raw in paths:
        target = (workspace / raw).resolve()
        try:
            target.relative_to(workspace)
        except ValueError:
            return f"File is outside the workspace: {raw}"
        if not target.is_file():
            return f"File not found: {raw}"
    return None


def _dry_run(workspace: Path, model: str, sandbox: str | None) -> int:
    """Check the workspace, sandbox, and model. Do not start a turn."""
    print_banner()
    print(f"Workspace: {workspace}")
    if not workspace.is_dir():
        print(f"Workspace does not exist: {workspace}", file=sys.stderr)
        return 1
    try:
        get_sandbox_runner(workspace, force_mode=sandbox)
    except (NotImplementedError, FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    mode = sandbox or os.environ.get("PARI_SANDBOX") or "auto"
    print(f"Sandbox: {mode}")
    try:
        get_provider(model)
    except (RuntimeError, NotImplementedError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Model: {model}")
    print("Self-check passed.")
    return 0


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pari-cli",
        description="PARI — Next-generation terminal coding agent.",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-w",
        "--workspace",
        type=str,
        default=None,
        help="Target project workspace directory (default: current working directory)",
    )
    parser.add_argument(
        "--sandbox",
        type=str,
        choices=["auto", "bwrap", "seatbelt", "cloud", "none"],
        default=None,
        help="Execution sandbox backend (default: auto, or PARI_SANDBOX)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (default: latest sign-in, or PARI_MODEL)",
    )
    parser.add_argument(
        "--edit-fallback",
        type=str,
        choices=["none", "cascade"],
        default="none",
        help="Edit engine fallback strategy when exact match fails (default: none)",
    )
    parser.add_argument(
        "--repomap",
        type=str,
        choices=["off", "ppr"],
        default="off",
        help="Repository AST PageRank symbol map (default: off, uses v1 ripgrep/glob)",
    )
    parser.add_argument(
        "--add",
        action="append",
        default=[],
        metavar="FILE",
        help="Pin reference documentation or file into context epoch",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate environment and exit without starting the loop",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommands")

    # pari find
    find_parser = subparsers.add_parser("find", help="Find files matching pattern")
    find_parser.add_argument(
        "pattern", type=str, default="*", nargs="?", help="File glob pattern"
    )
    find_parser.add_argument("-l", "--limit", type=int, default=100, help="Max results")

    # pari grep
    grep_parser = subparsers.add_parser(
        "grep", help="Search text across workspace files"
    )
    grep_parser.add_argument("query", type=str, help="Search string or regex")
    grep_parser.add_argument(
        "-r", "--regex", action="store_true", help="Treat query as a regular expression"
    )
    grep_parser.add_argument(
        "-f", "--filter", type=str, default="*", help="File path pattern filter"
    )
    grep_parser.add_argument("-l", "--limit", type=int, default=50, help="Max matches")

    login_parser = subparsers.add_parser(
        "login", help="Sign in with an API key or an account token"
    )
    login_parser.add_argument(
        "provider",
        nargs="?",
        choices=[info.id for info in PROVIDERS],
        help="Provider to sign in to",
    )
    login_parser.add_argument("--api-key", default=None, help="API key")
    login_parser.add_argument("--account", default=None, help="Account token")

    logout_parser = subparsers.add_parser("logout", help="Remove a saved sign-in")
    logout_parser.add_argument(
        "provider",
        nargs="?",
        choices=[info.id for info in PROVIDERS],
        help="Provider to sign out of",
    )

    # pari eval
    eval_parser = subparsers.add_parser("eval", help="Run benchmark evaluation suites")
    eval_parser.add_argument(
        "--suite",
        type=str,
        default="./evals/micro_suite.json",
        help="Path to evaluation benchmark suite JSON",
    )

    args = parser.parse_args(argv)

    if args.subcommand == "find":
        return cmd_find(args)
    elif args.subcommand == "grep":
        return cmd_grep(args)
    elif args.subcommand == "login":
        return cmd_login(args)
    elif args.subcommand == "logout":
        return cmd_logout(args)
    elif args.subcommand == "eval":
        return cmd_eval(args)
    else:
        return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
