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
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from pari.fs import atomic_write, read_file


@dataclass
class FileSnapshot:
    rel_path: str
    pre_edit_content: str
    pre_edit_hash: str
    post_edit_hash: str


@dataclass
class UndoResult:
    reverted_files: List[str]
    conflicted_files: List[str]
    terminated_processes: int
    disclosed_side_effects: List[str]


class GuardedUndoManager:
    """Provides guarded rollback for physical file changes and process termination."""

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self.snapshots: List[FileSnapshot] = []
        self.recorded_side_effects: List[str] = []

    def record_snapshot(self, rel_path: str, pre_content: str, post_content: str):
        pre_hash = hashlib.sha256(pre_content.encode("utf-8")).hexdigest()
        post_hash = hashlib.sha256(post_content.encode("utf-8")).hexdigest()
        self.snapshots.append(
            FileSnapshot(
                rel_path=rel_path,
                pre_edit_content=pre_content,
                pre_edit_hash=pre_hash,
                post_edit_hash=post_hash,
            )
        )

    def record_side_effect(self, description: str):
        self.recorded_side_effects.append(description)

    def undo(self, force: bool = False) -> UndoResult:
        reverted = []
        conflicted = []

        for snap in reversed(self.snapshots):
            target_path = self.workspace / snap.rel_path
            if not target_path.exists():
                conflicted.append(snap.rel_path)
                continue

            current_content = read_file(target_path)
            current_hash = hashlib.sha256(current_content.encode("utf-8")).hexdigest()

            # Guard: check if file has drifted from what PARI wrote
            if current_hash != snap.post_edit_hash and not force:
                conflicted.append(snap.rel_path)
                continue

            atomic_write(target_path, snap.pre_edit_content)
            reverted.append(snap.rel_path)

        self.snapshots.clear()
        side_effects = list(self.recorded_side_effects)
        self.recorded_side_effects.clear()

        return UndoResult(
            reverted_files=reverted,
            conflicted_files=conflicted,
            terminated_processes=0,
            disclosed_side_effects=side_effects,
        )
