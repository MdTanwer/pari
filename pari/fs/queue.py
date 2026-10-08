"""PARI Layer 6: File Mutation Queue.

Architectural Purpose:
    Harvested from Pi's file-mutation-queue.ts.
    Maintains a registry of asyncio.Lock primitives keyed by canonical realpath.
    Serializes concurrent writes to the same physical file while allowing parallel
    writes to distinct files.
"""

import asyncio
import os
from pathlib import Path

from pari.fs.atomic import atomic_write
from pari.fs.path import resolve_safe_path


class FileMutationQueue:
    """Serializes concurrent write mutations per canonical filesystem path."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = None if workspace is None else Path(workspace).resolve()
        self._locks: dict[str, asyncio.Lock] = {}
        self._registry = asyncio.Lock()

    async def get_lock(self, file_path: Path) -> asyncio.Lock:
        """Return the lock for this file's real path.

        A symlink and the file it points at share one lock, so two different
        path strings cannot write the same inode at once.
        """
        canonical = self._canonical(file_path)
        key = os.path.realpath(canonical)
        async with self._registry:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    async def write(self, file_path: Path, content: str) -> None:
        """Hold the file lock for the duration of the atomic replace."""
        lock = await self.get_lock(file_path)
        async with lock:
            target = self._canonical(file_path)
            await asyncio.to_thread(atomic_write, target, content)

    def _canonical(self, file_path: Path) -> Path:
        if self.workspace is None:
            return file_path.resolve()
        return resolve_safe_path(self.workspace, file_path)
