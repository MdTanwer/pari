"""Built-in permission rules, user rules, and the ask decision.

Ordinary project work runs with no prompt. A command that needs the network,
a git write, or a secret file asks unless a rule already allows or denies it.
A deny in either permission file wins, and it does not ask.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from pari.sandbox.base import SandboxLimits, is_package_install


_GIT_READ = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "blame",
        "ls-files",
        "rev-parse",
        "describe",
        "grep",
        "help",
        "version",
        "shortlog",
        "whatchanged",
        "name-rev",
        "cat-file",
        "rev-list",
        "merge-base",
        "check-ignore",
        "ls-remote",
        "var",
        "stripspace",
    }
)
_GIT_NETWORK = frozenset({"push", "fetch", "pull", "clone", "ls-remote", "submodule"})
_BRANCH_WRITE_FLAGS = frozenset(
    {
        "-d",
        "-D",
        "--delete",
        "-m",
        "-M",
        "--move",
        "-c",
        "-C",
        "--copy",
        "-u",
        "--set-upstream-to",
        "--unset-upstream",
        "--edit-description",
        "-f",
        "--force",
    }
)
_CONFIG_READ_FLAGS = frozenset(
    {"--get", "--get-all", "--get-regexp", "--list", "-l", "--show-origin"}
)
_GIT_OPT_WITH_ARG = frozenset(
    {
        "-C",
        "-c",
        "--git-dir",
        "--work-tree",
        "--namespace",
        "--config-env",
        "--super-prefix",
    }
)
_NETWORK_BINS = frozenset(
    {
        "curl",
        "wget",
        "ssh",
        "scp",
        "sftp",
        "ping",
        "nc",
        "ncat",
        "rsync",
        "ftp",
        "telnet",
        "dig",
        "nslookup",
    }
)
_SECRET_BINS = frozenset({"ssh", "scp", "sftp"})
_GH_LOCAL = frozenset({"help", "version", "completion"})
_SECRET_MARKERS = (".ssh", ".aws", ".gnupg", ".netrc", ".git-credentials")
_COMPOSERS = (";", "&&", "||", "|", "`", "$(", "\n", ">", "<")
_UNPARSED_WIDENING = re.compile(
    r"(?:^|[^\w.-])(curl|wget|ssh|scp|sftp|ping|nc|ncat|rsync|gh)"
    r"(?:$|[^\w.-])"
)


@dataclass(frozen=True)
class Grants:
    """Sandbox widenings one command needs."""

    network: bool = False
    git_write: bool = False
    secrets: bool = False
    github_token: bool = False

    def any(self) -> bool:
        return self.network or self.git_write or self.secrets or self.github_token

    def merge(self, other: Grants) -> Grants:
        return Grants(
            self.network or other.network,
            self.git_write or other.git_write,
            self.secrets or other.secrets,
            self.github_token or other.github_token,
        )


@dataclass(frozen=True)
class Rule:
    effect: str
    tool: str
    pattern: str


@dataclass(frozen=True)
class Decision:
    """What to do before a command starts."""

    action: str
    message: str
    command: str
    grants: Grants
    save_line: str
    package_network: bool
    read_only: bool

    def sandbox_limits(
        self,
        timeout: float,
        idle: float | None,
        granted_env: dict[str, str] | None = None,
    ) -> SandboxLimits:
        """Limits for a command that is allowed to run."""
        return SandboxLimits(
            timeout_seconds=timeout,
            daemon_idle_seconds=idle,
            allow_network=self.grants.network,
            allow_package_network=self.package_network,
            read_only=self.read_only,
            allow_git_write=self.grants.git_write and not self.read_only,
            allow_secrets=self.grants.secrets,
            granted_env=dict(granted_env or {}),
        )


class PermissionPolicy:
    """Rules from the project file and the home file."""

    def __init__(self, workspace: Path, home: Path):
        self.workspace = workspace
        self.home = home
        self.rules: list[Rule] = []
        self.read_only = False
        self.package_network = True

    @classmethod
    def load(cls, workspace: Path, home: Path | None = None) -> PermissionPolicy:
        policy = cls(Path(workspace).resolve(), Path.home() if home is None else home)
        project = policy.workspace / ".pari" / "permissions"
        home_file = policy.home / ".pari" / "permissions"
        policy._read(project)
        if home_file.resolve() != project.resolve():
            policy._read(home_file)
        return policy

    def decide(self, tool: str, command: str) -> Decision:
        """Allow, deny, or ask. A missing rule never counts as yes."""
        command = " ".join(command.split())
        grants = _grants_for(command)
        save_line = _save_line(tool, command)
        if self._denied(tool, command):
            return self._decision(
                "deny", "Permission denied by a rule.", command, Grants(), save_line
            )
        if self.read_only and grants.git_write:
            return self._decision(
                "deny", "This session is read-only.", command, Grants(), save_line
            )
        allowed = self._allowed(tool, command)
        if grants.any() and not allowed:
            message = _describe(command, grants)
            return self._decision("ask", message, command, grants, save_line)
        applied = grants if allowed else Grants()
        return self._decision("run", "", command, applied, save_line)

    def save_project_rule(self, line: str) -> None:
        """Append one allow line to the project file. A repeat is kept once."""
        path = self.workspace / ".pari" / "permissions"
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        if _line_present(existing, line):
            return
        prefix = "" if existing == "" or existing.endswith("\n") else "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{prefix}{line}\n")

    def _decision(
        self,
        action: str,
        message: str,
        command: str,
        grants: Grants,
        save_line: str,
    ) -> Decision:
        return Decision(
            action,
            message,
            command,
            grants,
            save_line,
            self.package_network,
            self.read_only,
        )

    def _denied(self, tool: str, command: str) -> bool:
        return any(
            self._matched(tool, segment, "deny") is not None
            for segment in _meaningful_segments(command)
        )

    def _allowed(self, tool: str, command: str) -> bool:
        segments = _meaningful_segments(command)
        if not segments:
            return False
        return all(
            self._matched(tool, segment, "allow") is not None for segment in segments
        )

    def _matched(self, tool: str, command: str, effect: str) -> Rule | None:
        for rule in self.rules:
            if rule.effect != effect or rule.tool != tool:
                continue
            if _command_matches(rule.pattern, command):
                return rule
        return None

    def _read(self, path: Path) -> None:
        if not path.is_file():
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line == "read-only":
                self.read_only = True
                continue
            parts = line.split()
            if parts[:2] == ["deny", "package-network"]:
                self.package_network = False
                continue
            if parts[:2] == ["allow", "package-network"]:
                continue
            if len(parts) >= 2 and parts[0] in {"allow", "deny"}:
                self.rules.append(Rule(parts[0], parts[1], " ".join(parts[2:])))


def normalize_choice(choice: str) -> str:
    """Map a prompt answer to once, repo, or no."""
    word = choice.strip().lower()
    if word == "once":
        return "once"
    if word in {"repo", "this repo", "this-repo"}:
        return "repo"
    return "no"


def _grants_for(command: str) -> Grants:
    segments = _segments(command)
    if segments is None:
        return _grants_unparsed(command)
    grants = Grants()
    for segment in segments:
        grants = grants.merge(_grants_simple(segment))
    return grants


def _grants_simple(command: str) -> Grants:
    if is_package_install(command):
        return Grants()
    try:
        parts = _skip_cd(_skip_env(shlex.split(command)))
    except ValueError:
        return Grants(network=True)
    if not parts:
        return Grants()
    binary = Path(parts[0]).name
    if binary == "gh":
        return _gh_grants(parts)
    sub = _git_subcommand(parts)
    network = binary in _NETWORK_BINS or sub in _GIT_NETWORK
    git_write = sub is not None and not _git_reads(sub, _args_after_subcommand(parts))
    if _writes_git_dir(binary, command):
        git_write = True
    secrets = binary in _SECRET_BINS or _mentions_secret(command)
    return Grants(network, git_write, secrets, github_token=sub in _GIT_NETWORK)


def _gh_grants(parts: list[str]) -> Grants:
    """Every gh command except help talks to the GitHub API with the token."""
    words = _gh_words(parts)
    if not words or words[0] in _GH_LOCAL:
        return Grants()
    return Grants(network=True, github_token=True)


def _gh_words(parts: list[str]) -> list[str]:
    """Subcommand words before the first flag: gh pr create -t x -> pr, create."""
    words: list[str] = []
    for token in parts[1:]:
        if token.startswith("-") or len(words) == 2:
            break
        words.append(token)
    return words


def _grants_unparsed(command: str) -> Grants:
    """A substitution or redirect hides the real program. Ask if it looks wide."""
    grants = _grants_simple(command)
    for match in re.finditer(r"(?:^|[\s;&|])((?:git|gh)\s+.*)", command):
        grants = grants.merge(_grants_simple(match.group(1)))
    if grants.any():
        return grants
    if _UNPARSED_WIDENING.search(command):
        return Grants(network=True)
    if _mentions_secret(command):
        return Grants(secrets=True)
    return Grants()


def _save_line(tool: str, command: str) -> str:
    try:
        parts = _skip_cd(_skip_env(shlex.split(command)))
    except ValueError:
        parts = []
    if not parts:
        return f"allow {tool} {command}"
    binary = Path(parts[0]).name
    sub = _git_subcommand(parts)
    if binary == "git" and sub:
        return f"allow {tool} git {sub}"
    if binary == "gh" and _gh_words(parts):
        return f"allow {tool} gh {' '.join(_gh_words(parts))}"
    if _has_composer(command):
        return f"allow {tool} {command}"
    if len(parts) > 1:
        return f"allow {tool} {binary} *"
    return f"allow {tool} {binary}"


def _describe(command: str, grants: Grants) -> str:
    return f"{command} needs {needs_phrase(grants)}"


def needs_phrase(grants: Grants) -> str:
    parts: list[str] = []
    if grants.network:
        parts.append("network")
    if grants.git_write:
        parts.append("a git write")
    if grants.secrets:
        parts.append("access to secret files")
    if grants.github_token:
        parts.append("your GitHub token")
    if len(parts) <= 1:
        return parts[0] if parts else "permission"
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _command_matches(pattern: str, command: str) -> bool:
    pattern = pattern.strip()
    if not pattern:
        return True
    if pattern.endswith("*"):
        prefix = pattern[:-1].rstrip()
        if not prefix:
            return True
        return command == prefix or command.startswith(prefix + " ")
    try:
        wanted = shlex.split(pattern)
        got = _skip_cd(_skip_env(shlex.split(command)))
    except ValueError:
        return command == pattern
    if not wanted:
        return True
    if Path(wanted[0]).name == "git" and len(wanted) >= 2:
        return _git_matches(wanted, got)
    if len(got) < len(wanted):
        return False
    head = [Path(got[0]).name, *got[1 : len(wanted)]]
    return head == [Path(wanted[0]).name, *wanted[1:]]


def _git_reads(sub: str, args: list[str]) -> bool:
    """List and show forms of subcommands that can also change the repository."""
    if sub in _GIT_READ:
        return True
    flags_only = all(arg.startswith("-") for arg in args)
    if sub == "branch":
        listing = {"--list", "-l"} & set(args)
        changes = _BRANCH_WRITE_FLAGS & set(args)
        return not changes and (flags_only or bool(listing))
    if sub == "tag":
        return not args or bool({"--list", "-l"} & set(args))
    if sub == "remote":
        return flags_only or args[0] == "get-url"
    if sub == "config":
        return bool(_CONFIG_READ_FLAGS & set(args))
    if sub in {"stash", "worktree"}:
        return bool(args) and args[0] == "list"
    if sub == "reflog":
        return not args or args[0] == "show"
    return False


def _git_matches(wanted: list[str], got: list[str]) -> bool:
    """``git push`` matches ``git push origin`` and ``git -C repo push``."""
    if not got or Path(got[0]).name != "git":
        return False
    if _git_subcommand(got) != wanted[1]:
        return False
    if len(wanted) == 2:
        return True
    args = _args_after_subcommand(got)
    extra = wanted[2:]
    return args[: len(extra)] == extra


def _args_after_subcommand(parts: list[str]) -> list[str]:
    index = 1
    while index < len(parts):
        token = parts[index]
        if token in _GIT_OPT_WITH_ARG:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return parts[index + 1 :]
    return []


def _git_subcommand(parts: list[str]) -> str | None:
    if not parts or Path(parts[0]).name != "git":
        return None
    index = 1
    while index < len(parts):
        token = parts[index]
        if token in _GIT_OPT_WITH_ARG:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token
    return None


def _segments(command: str) -> list[str] | None:
    """Split on ; && || and pipes. None when a quote, redirect, or $( hides one."""
    if not _has_composer(command):
        return [command]
    parts: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(command):
        char = command[index]
        if quote is not None:
            buf.append(char)
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            buf.append(char)
            index += 1
            continue
        if command.startswith("$(", index) or char in {"`", "<"}:
            return None
        if char == ">" and not _is_fd_redirect(command, index):
            return None
        if command.startswith(("&&", "||"), index):
            parts.append("".join(buf))
            buf = []
            index += 2
            continue
        if char in {";", "|", "\n"}:
            parts.append("".join(buf))
            buf = []
            index += 1
            continue
        buf.append(char)
        index += 1
    if quote is not None:
        return None
    parts.append("".join(buf))
    return [part.strip() for part in parts if part.strip()]


def _has_composer(command: str) -> bool:
    return any(marker in command for marker in _COMPOSERS)


def _mentions_secret(command: str) -> bool:
    lowered = command.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def _is_fd_redirect(command: str, index: int) -> bool:
    """``2>&1`` and ``>&2`` are fd copies. They do not hide a later git or gh."""
    return command.startswith(">&", index)


def _writes_git_dir(binary: str, command: str) -> bool:
    """touch/rm/mkdir on .git is a git write, even though the binary is not git."""
    if binary in {"git", "gh"}:
        return False
    if binary not in {"touch", "mkdir", "rm", "mv", "cp", "chmod", "ln"}:
        return False
    return bool(re.search(r"(?:^|[\s/=])\.git(?:/|\s|$)", command))


_PIPE_READERS = frozenset({"head", "tail", "grep", "cat", "wc", "sort", "uniq"})


def _meaningful_segments(command: str) -> list[str]:
    """Commands that can widen the sandbox. cd and ``| head`` are ignored."""
    segments = _segments(command)
    if segments is None:
        return [command]
    kept: list[str] = []
    for segment in segments:
        try:
            parts = _skip_cd(_skip_env(shlex.split(segment)))
        except ValueError:
            kept.append(segment)
            continue
        if not parts:
            continue
        if Path(parts[0]).name in _PIPE_READERS:
            continue
        kept.append(segment)
    return kept or [command]


def _skip_cd(parts: list[str]) -> list[str]:
    """Drop a leading ``cd dir`` so ``cd dir && git add`` is classified as git."""
    if not parts or Path(parts[0]).name != "cd":
        return parts
    index = 1
    if index < len(parts) and parts[index] not in {"&&", "||", ";"}:
        index += 1
    while index < len(parts) and parts[index] in {"&&", "||", ";"}:
        index += 1
    return _skip_env(parts[index:])


def _skip_env(parts: list[str]) -> list[str]:
    index = 0
    while index < len(parts) and _is_assignment(parts[index]):
        index += 1
    return parts[index:]


def _is_assignment(token: str) -> bool:
    if "=" not in token or token.startswith("="):
        return False
    name = token.split("=", 1)[0]
    return name.replace("_", "").isalnum() and not name[:1].isdigit()


def _line_present(text: str, line: str) -> bool:
    return any(item.strip() == line for item in text.splitlines())
