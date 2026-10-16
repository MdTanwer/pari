"""Identity and GitHub token for an approved command."""

import os
import subprocess
from pathlib import Path

import pytest

from pari.permissions.credentials import (
    git_identity,
    github_credentials,
    github_token,
    granted_env,
)
from pari.permissions.policy import Grants


def _fill(host: str, env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    child = {
        "PATH": os.environ["PATH"],
        "HOME": str(cwd),
        "GIT_CONFIG_NOSYSTEM": "1",
        **env,
    }
    return subprocess.run(
        ["git", "credential", "fill"],
        input=f"protocol=https\nhost={host}\n\n",
        capture_output=True,
        text=True,
        env=child,
        cwd=cwd,
        timeout=10,
        check=False,
    )


def test_token_is_offered_to_github_only(tmp_path: Path):
    env = github_credentials("tok-123")
    github = _fill("github.com", env, tmp_path)
    assert github.returncode == 0, github.stderr
    assert "username=x-access-token" in github.stdout
    assert "password=tok-123" in github.stdout
    other = _fill("example.com", env, tmp_path)
    assert "tok-123" not in other.stdout
    assert other.returncode != 0


def test_github_token_prefers_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GH_TOKEN", "from-env")
    assert github_token() == "from-env"


def test_identity_comes_from_the_host(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Ada")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "ada@example.com")
    env = git_identity(tmp_path)
    assert env["GIT_COMMITTER_NAME"] == "Ada"
    assert env["GIT_COMMITTER_EMAIL"] == "ada@example.com"


def test_nothing_is_passed_without_a_grant(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "secret")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Ada")
    assert granted_env(Grants(network=True), tmp_path) == {}
    commit = granted_env(Grants(git_write=True), tmp_path)
    assert "GH_TOKEN" not in commit
    assert commit["GIT_AUTHOR_NAME"] == "Ada"
    push = granted_env(
        Grants(network=True, git_write=True, github_token=True), tmp_path
    )
    assert push["GH_TOKEN"] == "secret"
