"""Values passed into one approved command.

The sandbox starts from a clean environment and hides the user's git config.
After the user approves a git write, the commit still needs a name and email.
After the user approves a push, fetch, or pull, git needs a GitHub token.
These are looked up on the host and handed to that command only.
"""

import os
import subprocess
from pathlib import Path

from pari.permissions.policy import Grants


# The helper is scoped to github.com, so the token is never offered to
# another remote. It answers only "get" requests.
_GITHUB_HELPER = (
    '!f() { test "$1" = get || return 0; '
    "echo username=x-access-token; "
    'echo "password=$GH_TOKEN"; }; f'
)
_IDENTITY_ENV = (
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
)


def granted_env(grants: Grants, workspace: Path) -> dict[str, str]:
    """Environment for a command whose grants the user approved."""
    env: dict[str, str] = {}
    if grants.git_write:
        env.update(git_identity(workspace))
    if grants.github_token:
        token = github_token()
        if token:
            env.update(github_credentials(token))
    return env


def git_identity(workspace: Path) -> dict[str, str]:
    """Author and committer from the host, or nothing if git has none."""
    env = {key: os.environ[key] for key in _IDENTITY_ENV if os.environ.get(key)}
    name = env.get("GIT_AUTHOR_NAME") or _git_config(workspace, "user.name")
    email = env.get("GIT_AUTHOR_EMAIL") or _git_config(workspace, "user.email")
    if name:
        env.setdefault("GIT_AUTHOR_NAME", name)
        env.setdefault("GIT_COMMITTER_NAME", name)
    if email:
        env.setdefault("GIT_AUTHOR_EMAIL", email)
        env.setdefault("GIT_COMMITTER_EMAIL", email)
    return env


def github_token() -> str | None:
    """GH_TOKEN, then GITHUB_TOKEN, then the signed-in gh CLI."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return _run(["gh", "auth", "token"], cwd=None)


def github_credentials(token: str) -> dict[str, str]:
    return {
        "GH_TOKEN": token,
        "GITHUB_TOKEN": token,
        "GH_PROMPT_DISABLED": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "credential.https://github.com.helper",
        "GIT_CONFIG_VALUE_0": "",
        "GIT_CONFIG_KEY_1": "credential.https://github.com.helper",
        "GIT_CONFIG_VALUE_1": _GITHUB_HELPER,
    }


def _git_config(workspace: Path, key: str) -> str | None:
    return _run(["git", "config", "--get", key], cwd=workspace)


def _run(argv: list[str], cwd: Path | None) -> str | None:
    """Read one value from a host tool. Any failure means no value."""
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        return None
    return value
