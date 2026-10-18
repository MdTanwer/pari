"""Unit tests for pari.fs safe path resolution and atomic writes."""

import asyncio
import os
import stat
from pathlib import Path

import pytest

from pari.fs import (
    BinaryFileError,
    FileMutationQueue,
    atomic_write,
    read_file,
    resolve_safe_path,
    resolve_writable_path,
)


def test_resolve_safe_path_valid(tmp_path: Path):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("print('hello')")

    safe = resolve_safe_path(tmp_path, "src/app.py")
    assert safe == target.resolve()


def test_resolve_safe_path_traversal_rejected(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Attempt to traverse outside workspace
    with pytest.raises(PermissionError, match="Path traversal rejected"):
        resolve_safe_path(workspace, "../secret.txt")


def test_resolve_safe_path_prefix_collision_rejected(tmp_path: Path):
    # Ensure /workspace2 is not mistaken for being inside /workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    sibling = tmp_path / "workspace_evil"
    sibling.mkdir()
    evil_file = sibling / "payload.py"
    evil_file.write_text("evil")

    with pytest.raises(PermissionError, match="Path traversal rejected"):
        resolve_safe_path(workspace, "../workspace_evil/payload.py")


def test_resolve_writable_path_rejects_git_and_pari(tmp_path: Path):
    with pytest.raises(PermissionError, match="reserved"):
        resolve_writable_path(tmp_path, ".git/hooks/pre-commit")
    with pytest.raises(PermissionError, match="reserved"):
        resolve_writable_path(tmp_path, ".pari/sessions/abc.jsonl")


def test_resolve_writable_path_rejects_dotdot_and_symlink(tmp_path: Path):
    (tmp_path / "src").mkdir()
    with pytest.raises(PermissionError, match="reserved"):
        resolve_writable_path(tmp_path, "src/../.git/hooks/pre-commit")

    git = tmp_path / ".git"
    git.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(git, target_is_directory=True)
    with pytest.raises(PermissionError, match="reserved"):
        resolve_writable_path(tmp_path, "alias/hooks/pre-commit")


def test_resolve_writable_path_allows_a_normal_file_and_gitignore(tmp_path: Path):
    safe = resolve_writable_path(tmp_path, "src/app.py")
    assert safe == (tmp_path / "src" / "app.py").resolve()
    gitignore = resolve_writable_path(tmp_path, ".gitignore")
    assert gitignore == (tmp_path / ".gitignore").resolve()
    workflows = resolve_writable_path(tmp_path, ".github/workflows/ci.yml")
    assert workflows == (tmp_path / ".github" / "workflows" / "ci.yml").resolve()


def test_resolve_safe_path_still_allows_a_git_read(tmp_path: Path):
    target = tmp_path / ".git" / "HEAD"
    target.parent.mkdir()
    target.write_text("ref: refs/heads/main\n")
    assert resolve_safe_path(tmp_path, ".git/HEAD") == target.resolve()


def test_read_file_rejects_nul_in_the_first_kilobyte(tmp_path: Path):
    target = tmp_path / "icon.png"
    target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
    with pytest.raises(BinaryFileError, match="Binary file"):
        read_file(target)


def test_read_file_rejects_bytes_that_are_not_utf8(tmp_path: Path):
    target = tmp_path / "blob.bin"
    target.write_bytes(b"\xff\xfe")
    with pytest.raises(BinaryFileError, match="Binary file"):
        read_file(target)


def test_atomic_write(tmp_path: Path):
    target = tmp_path / "output.txt"
    content = "Hello, PARI atomic write!\nLine 2\n"

    atomic_write(target, content)
    assert target.exists()
    assert read_file(target) == content


def test_atomic_write_preserves_the_mode_of_an_existing_file(tmp_path: Path):
    target = tmp_path / "run.sh"
    target.write_text("#!/bin/sh\necho hi\n")
    os.chmod(target, 0o755)

    atomic_write(target, "#!/bin/sh\necho bye\n")

    assert stat.S_IMODE(target.stat().st_mode) == 0o755


def test_atomic_write_gives_a_new_file_the_umask_default(tmp_path: Path):
    target = tmp_path / "fresh.txt"
    umask = os.umask(0)
    os.umask(umask)

    atomic_write(target, "hello\n")

    assert stat.S_IMODE(target.stat().st_mode) == 0o666 & ~umask


@pytest.mark.asyncio
async def test_symlink_and_target_share_one_lock(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "auth.py"
    target.write_text("x")
    alias = workspace / "alias.py"
    alias.symlink_to(target)
    queue = FileMutationQueue(workspace)
    assert await queue.get_lock(target) is await queue.get_lock(alias)


@pytest.mark.asyncio
async def test_writes_to_one_file_do_not_interleave(tmp_path: Path):
    queue = FileMutationQueue(tmp_path)
    target = tmp_path / "notes.txt"
    order: list[str] = []

    async def write(label: str, body: str) -> None:
        lock = await queue.get_lock(target)
        async with lock:
            order.append(f"start-{label}")
            await asyncio.sleep(0.01)
            atomic_write(target, body)
            order.append(f"end-{label}")

    await asyncio.gather(write("a", "A\n"), write("b", "B\n"))
    assert order in (
        ["start-a", "end-a", "start-b", "end-b"],
        ["start-b", "end-b", "start-a", "end-a"],
    )
    assert read_file(target) in {"A\n", "B\n"}


@pytest.mark.asyncio
async def test_queue_write_refuses_a_git_hook(tmp_path: Path):
    queue = FileMutationQueue(tmp_path)
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    with pytest.raises(PermissionError, match="reserved"):
        await queue.write(Path(".git/hooks/pre-commit"), "#!/bin/sh\n")
    assert not hook.exists()
    assert not (tmp_path / ".git").exists()
