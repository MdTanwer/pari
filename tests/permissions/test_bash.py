"""The bash tool asks before it widens the sandbox."""

import subprocess
from pathlib import Path

import pytest

from pari.permissions.policy import Decision
from pari.tools.bash import BashTool
from pari.tools.registry import get_default_registry


@pytest.mark.asyncio
async def test_a_missing_prompt_denies_a_widening(tmp_path: Path):
    tool = BashTool(tmp_path, permission_home=tmp_path / "home")
    result = await tool.execute("git push")
    assert result["denied"] is True
    assert "needs network, a git write" in result["output"]
    assert not (tmp_path / ".pari" / "permissions").exists()


@pytest.mark.asyncio
async def test_no_does_not_save_a_rule(tmp_path: Path):
    tool = BashTool(tmp_path, permission_home=tmp_path / "home")

    async def refuse(_decision: Decision) -> str:
        return "no"

    tool.ask_permission = refuse
    result = await tool.execute("curl https://example.com")
    assert result["denied"] is True
    assert not (tmp_path / ".pari" / "permissions").exists()


@pytest.mark.asyncio
async def test_this_repo_saves_the_allow_and_runs(tmp_path: Path):
    tool = BashTool(tmp_path, permission_home=tmp_path / "home")

    async def allow_repo(decision: Decision) -> str:
        assert decision.grants.git_write is True
        return "repo"

    tool.ask_permission = allow_repo
    result = await tool.execute("git commit --allow-empty -m hi")
    saved = (tmp_path / ".pari" / "permissions").read_text()
    assert saved == "allow bash git commit\n"
    assert result.get("denied") is not True
    assert "Permission denied" not in result["output"]


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.mark.asyncio
async def test_approved_commit_and_push_run_in_the_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Ada")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "ada@example.com")
    monkeypatch.setenv("GH_TOKEN", "unused-for-a-local-remote")
    _git(tmp_path, "init", "-q", "--bare", "remote.git")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "remote", "add", "origin", str(tmp_path / "remote.git"))
    (tmp_path / "a.txt").write_text("hi\n")
    asked: list[str] = []

    async def approve_once(decision: Decision) -> str:
        asked.append(decision.message)
        return "once"

    tool = BashTool(tmp_path, permission_home=tmp_path / "home")
    tool.ask_permission = approve_once
    for command in (
        "git add a.txt",
        "git commit -q -m first",
        "git push -q origin main",
    ):
        result = await tool.execute(command)
        assert result["exit_code"] == 0, result["output"]
    assert len(asked) == 3
    assert "your GitHub token" in asked[2]
    pushed = _git(tmp_path / "remote.git", "log", "--format=%an %s", "main")
    assert pushed == "Ada first"


@pytest.mark.asyncio
async def test_read_only_blocks_writes(tmp_path: Path):
    pari = tmp_path / ".pari"
    pari.mkdir()
    (pari / "permissions").write_text("read-only\n")
    registry = get_default_registry(tmp_path)
    written = await registry.execute(
        "write_file", {"path": "hello.txt", "content": "nope"}
    )
    assert written == "This session is read-only."
    assert not (tmp_path / "hello.txt").exists()

    target = tmp_path / "keep.txt"
    target.write_text("stay")
    edited = await registry.execute(
        "edit_file",
        {"path": "keep.txt", "search": "stay", "replace": "changed"},
    )
    assert edited["status"] == "denied"
    assert target.read_text() == "stay"
