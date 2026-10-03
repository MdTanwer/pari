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


class GuardedUndoManager:
    """Provides guarded rollback for physical file changes and process termination."""

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        # TODO: Initialize snapshot storage and side-effects audit log

    def record_snapshot(self, rel_path: str, pre_content: str, post_content: str):
        """Record file state prior to write mutation."""
        raise NotImplementedError

    def record_side_effect(self, description: str):
        """Log external irreversible side effect (e.g. package install, DB migration)."""
        raise NotImplementedError

    def undo(self, force: bool = False) -> UndoResult:
        """Execute guarded rollback verifying files haven't drifted."""
        raise NotImplementedError
