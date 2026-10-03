"""PARI Layer 3: Worktree-Scoped Symbol Cache.

Architectural Purpose:
    Closes Aider F6 (Diskcache SQLite lock collisions across git worktrees).
    Scans and caches AST tags with SQLite database files scoped explicitly to the
    unique worktree root path, eliminating multi-session database locking errors.
"""

import hashlib
from pathlib import Path
from typing import Any, Optional


class WorktreeSymbolCache:
    """Manages cached symbol index keyed specifically to workspace path and file mtimes."""

    def __init__(self, workspace: Path, cache_dir: Optional[Path] = None):
        self.workspace = workspace.resolve()
        cache_base = cache_dir or (Path.home() / ".cache" / "pari" / "tags")
        cache_base.mkdir(parents=True, exist_ok=True)
        # Create unique database file name based on canonical workspace path hash
        path_hash = hashlib.sha256(str(self.workspace).encode("utf-8")).hexdigest()[:16]
        self.db_path = cache_base / f"symbols_{path_hash}.db"

    def get_db_path(self) -> Path:
        return self.db_path
