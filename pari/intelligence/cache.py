"""PARI Layer 3: Worktree-Scoped Symbol Cache.

Architectural Purpose:
    Closes Aider F6 (Diskcache SQLite lock collisions across git worktrees).
    Scans and caches AST tags with SQLite database files scoped explicitly to the
    unique worktree root path, eliminating multi-session database locking errors.
"""

import hashlib
import json
import sqlite3
from pathlib import Path


class WorktreeSymbolCache:
    """Cache symbols for one workspace. Another worktree gets another file."""

    def __init__(self, workspace: Path, cache_dir: Path | None = None):
        self.workspace = workspace.resolve()
        self.cache_dir = cache_dir

    def get_db_path(self) -> Path:
        """Return the sqlite file for this workspace path."""
        directory = self.cache_dir or (self.workspace / ".pari")
        directory.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(str(self.workspace).encode()).hexdigest()[:16]
        return directory / f"tags.{key}.cache.v1.sqlite"

    def get_symbols(self, relative_path: str, mtime: float) -> list[dict] | None:
        """Return cached symbols when the file's mtime is unchanged."""
        path = self.get_db_path()
        if not path.exists():
            return None
        with sqlite3.connect(path) as conn:
            _ensure(conn)
            row = conn.execute(
                "SELECT mtime, payload FROM symbols WHERE path = ?",
                (relative_path,),
            ).fetchone()
        if row is None or row[0] != mtime:
            return None
        loaded = json.loads(row[1])
        if not isinstance(loaded, list):
            return None
        return loaded

    def put_symbols(
        self, relative_path: str, mtime: float, symbols: list[dict]
    ) -> None:
        """Store symbols for one file at one mtime."""
        path = self.get_db_path()
        with sqlite3.connect(path) as conn:
            _ensure(conn)
            conn.execute(
                "INSERT INTO symbols(path, mtime, payload) VALUES (?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET mtime = excluded.mtime, "
                "payload = excluded.payload",
                (relative_path, mtime, json.dumps(symbols)),
            )


def _ensure(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS symbols ("
        "path TEXT PRIMARY KEY, mtime REAL NOT NULL, payload TEXT NOT NULL)"
    )
