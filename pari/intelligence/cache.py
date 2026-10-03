"""PARI Layer 3: Worktree-Scoped Symbol Cache.

Architectural Purpose:
    Closes Aider F6 (Diskcache SQLite lock collisions across git worktrees).
    Scans and caches AST tags with SQLite database files scoped explicitly to the
    unique worktree root path, eliminating multi-session database locking errors.
"""

from pathlib import Path
from typing import Optional


class WorktreeSymbolCache:
    """Manages cached symbol index keyed specifically to workspace path and file mtimes."""

    def __init__(self, workspace: Path, cache_dir: Optional[Path] = None):
        self.workspace = workspace.resolve()

    def get_db_path(self) -> Path:
        """Return path to workspace-isolated SQLite cache file."""
        raise NotImplementedError
