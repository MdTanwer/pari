"""Filesystem operations with strict path containment and atomic replacement."""

import os
import tempfile
from pathlib import Path


def resolve_safe_path(workspace_root: Path, target_path: str) -> Path:
    """Resolve a target path and strictly verify it is contained within workspace_root.
    
    Raises:
        PermissionError: If target_path escapes outside workspace_root.
    """
    workspace_resolved = workspace_root.resolve()
    target_resolved = (workspace_root / target_path).resolve()
    
    try:
        target_resolved.relative_to(workspace_resolved)
    except ValueError:
        raise PermissionError(
            f"Path traversal rejected: '{target_path}' resolves outside workspace '{workspace_resolved}'"
        )
    return target_resolved


def read_file(file_path: Path) -> str:
    """Read full text content of a file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def atomic_write(file_path: Path, content: str) -> None:
    """Atomically write content to file_path using tempfile + os.replace.
    
    Guarantees the file is never observed in a torn or partially written state.
    """
    parent_dir = file_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    
    fd, temp_file = tempfile.mkstemp(dir=parent_dir, prefix=".pari_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, file_path)
    except Exception:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise
