"""PARI Layer 6: Atomic File Write and Sync Protocol.

Architectural Purpose:
    Closes Claude Code F1 & F3.
    Writes content to a temporary file in the same directory (guaranteeing same filesystem device),
    calls os.fsync() on the file descriptor, atomically replaces the target via os.replace(),
    and flushes the parent directory entry with fsync on POSIX.
"""

import os
import tempfile
from pathlib import Path


def atomic_write(target_path: Path, content: str) -> None:
    """Atomically write content to target_path, preventing partial/torn writes."""
    target = target_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temporary file in the same directory (same filesystem device)
    fd, temp_path = tempfile.mkstemp(dir=target.parent, prefix=".pari_tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        # Atomic replacement
        os.replace(temp_path, target)

        # Sync parent directory on POSIX
        if os.name == "posix":
            try:
                parent_fd = os.open(str(target.parent), os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
            except (OSError, PermissionError):
                pass
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise


def read_file(file_path: Path) -> str:
    """Read full text content of a file."""
    return file_path.resolve().read_text(encoding="utf-8")

