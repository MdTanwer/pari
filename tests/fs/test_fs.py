"""Unit tests for pari.fs safe path resolution and atomic writes."""

import asyncio
from pathlib import Path

import pytest

from pari.fs import FileMutationQueue, atomic_write, read_file, resolve_safe_path


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


def test_atomic_write(tmp_path: Path):
    target = tmp_path / "output.txt"
    content = "Hello, PARI atomic write!\nLine 2\n"

    atomic_write(target, content)
    assert target.exists()
    assert read_file(target) == content


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
