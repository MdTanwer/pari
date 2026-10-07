"""Unit tests for pari.fs safe path resolution and atomic writes."""

from pathlib import Path

import pytest

from pari.fs import atomic_write, read_file, resolve_safe_path


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
