"""PARI Layer 6: Atomic File Write and Sync Protocol.

Architectural Purpose:
    Closes Claude Code F1 & F3.
    Writes content to a temporary file in the same directory (guaranteeing same filesystem device),
    calls os.fsync() on the file descriptor, atomically replaces the target via os.replace(),
    and flushes the parent directory entry with fsync on POSIX.
"""

import os
from pathlib import Path
import tempfile


def atomic_write(target_path: Path, content: str) -> None:
    """Atomically write content to target_path, preventing partial/torn writes."""
    target_path = target_path.resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    parent_dir = target_path.parent

    # Create temporary file in the same parent directory
    with tempfile.NamedTemporaryFile("w", dir=parent_dir, delete=False, encoding="utf-8") as temp_file:
        temp_name = temp_file.name
        temp_file.write(content)
        temp_file.flush()
        os.fsync(temp_file.fileno())

    try:
        # Atomic rename replacing destination
        os.replace(temp_name, target_path)

        # Sync parent directory to persist directory entry on POSIX
        if os.name == "posix":
            try:
                parent_fd = os.open(str(parent_dir), os.O_RDONLY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
            except OSError:
                pass
    finally:
        if os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def read_file(file_path: Path) -> str:
    """Read full text content of a file."""
    return file_path.read_text(encoding="utf-8")
