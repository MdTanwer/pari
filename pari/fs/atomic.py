"""PARI Layer 6: Atomic File Write and Sync Protocol.

Architectural Purpose:
    Closes Claude Code F1 & F3.
    Writes content to a temporary file in the same directory (guaranteeing same filesystem device),
    calls os.fsync() on the file descriptor, atomically replaces the target via os.replace(),
    and flushes the parent directory entry with fsync on POSIX.
"""

from pathlib import Path


def atomic_write(target_path: Path, content: str) -> None:
    """Atomically write content to target_path, preventing partial/torn writes."""
    raise NotImplementedError


def read_file(file_path: Path) -> str:
    """Read full text content of a file."""
    raise NotImplementedError
