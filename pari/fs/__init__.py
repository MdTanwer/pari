"""PARI Layer 6: Concurrency and File Safety Engine.

Architectural Purpose:
    Closes Claude Code F3 (File write race conditions tearing files during parallel
    operations)
    and path traversal / prefix collision vulnerabilities.

Subsystems:
    - path: Canonical path resolution via Path.resolve().relative_to()
    - atomic: Atomic write using temporary file + os.replace() + directory os.fsync()
    - queue: FileMutationQueue maintaining per-canonical-realpath asyncio locks
"""

from pari.fs.atomic import atomic_write, read_file
from pari.fs.path import resolve_safe_path


__all__ = ["resolve_safe_path", "atomic_write", "read_file"]
