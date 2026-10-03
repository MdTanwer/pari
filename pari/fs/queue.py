"""PARI Layer 6: File Mutation Queue.

Architectural Purpose:
    Harvested from Pi's file-mutation-queue.ts.
    Maintains a registry of asyncio.Lock primitives keyed by canonical realpath.
    Serializes concurrent writes to the same physical file while allowing parallel
    writes to distinct files.
"""

import asyncio
from pathlib import Path


class FileMutationQueue:
    """Serializes concurrent write mutations per canonical filesystem path."""

    def __init__(self):
        pass

    async def get_lock(self, file_path: Path) -> asyncio.Lock:
        """Get canonical per-path lock."""
        raise NotImplementedError
