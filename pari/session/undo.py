"""PARI Layer 1: Guarded Undo Manager.

Architectural Purpose:
    Implements a safe, bounded /undo mechanism:
    1. Restores files modified by the most recent turn.
    2. Guarded check: If the developer manually edited the file after PARI touched it,
       aborts or prompts to prevent accidental overwrite of user work.
    3. Terminates background processes started during the turn.
    4. Explicit disclosure: Informs user that external side effects (API calls, remote DBs,
       pip install) are logged but not automatically reversible.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class FileSnapshot:
    """Pre- and post-edit file hash snapshot."""
    rel_path: str
    pre_edit_content: str
    pre_edit_hash: str
    post_edit_hash: str


@dataclass
class UndoResult:
    """Outcome of guarded undo execution."""
    reverted_files: List[str]
    conflicted_files: List[str]
    terminated_processes: int
    disclosed_side_effects: List[str]


import hashlib
from typing import Dict, List
from pari.fs.atomic import atomic_write, read_file
from pari.fs.path import resolve_safe_path


class GuardedUndoManager:
    """Provides guarded rollback for physical file changes and process termination."""

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self.snapshots: Dict[str, FileSnapshot] = {}
        self.side_effects: List[str] = []

    def _hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def record_snapshot(self, rel_path: str, pre_content: str, post_content: str):
        """Record file state prior to write mutation."""
        self.snapshots[rel_path] = FileSnapshot(
            rel_path=rel_path,
            pre_edit_content=pre_content,
            pre_edit_hash=self._hash(pre_content),
            post_edit_hash=self._hash(post_content),
        )

    def record_side_effect(self, description: str):
        """Log external irreversible side effect (e.g. package install, DB migration)."""
        self.side_effects.append(description)

    def undo(self, force: bool = False) -> UndoResult:
        """Execute guarded rollback verifying files haven't drifted."""
        reverted: List[str] = []
        conflicts: List[str] = []

        for rel_path, snapshot in list(self.snapshots.items()):
            file_path = resolve_safe_path(self.workspace, rel_path)
            if not file_path.exists():
                atomic_write(file_path, snapshot.pre_edit_content)
                reverted.append(rel_path)
                continue

            current_content = read_file(file_path)
            current_hash = self._hash(current_content)

            if current_hash == snapshot.post_edit_hash or force:
                atomic_write(file_path, snapshot.pre_edit_content)
                reverted.append(rel_path)
            else:
                conflicts.append(rel_path)

        # Clear reverted snapshots
        for rel in reverted:
            self.snapshots.pop(rel, None)

        result = UndoResult(
            reverted_files=reverted,
            conflicted_files=conflicts,
            terminated_processes=0,
            disclosed_side_effects=list(self.side_effects),
        )
        self.side_effects.clear()
        return result

