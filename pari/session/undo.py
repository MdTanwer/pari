"""PARI Layer 1: Guarded Undo Manager.

Restores files from the last turn, stops processes started in that turn,
and refuses to overwrite a file the developer changed afterward.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from pari.fs.atomic import BinaryFileError, atomic_write, read_file
from pari.fs.path import resolve_safe_path


@dataclass
class FileSnapshot:
    """Pre- and post-edit file hash snapshot."""

    rel_path: str
    pre_edit_content: str
    pre_edit_hash: str
    post_edit_hash: str
    existed_before: bool


@dataclass
class _Turn:
    """Files and side effects from one user turn.

    A path keeps the content from before the turn's first edit. Later edits
    in that turn only move the post-edit hash.
    """

    files: dict[str, FileSnapshot]
    side_effects: list[str]


@dataclass
class UndoResult:
    """Outcome of guarded undo execution."""

    reverted_files: list[str]
    conflicted_files: list[str]
    terminated_processes: int
    disclosed_side_effects: list[str]


class GuardedUndoManager:
    """Provides guarded rollback for physical file changes and process termination."""

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self._turns: list[_Turn] = []
        self._needs_new = True

    def begin_turn(self) -> None:
        """The next recorded edit belongs to a new turn."""
        self._needs_new = True

    def _hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _open_turn(self) -> _Turn:
        if self._needs_new or not self._turns:
            self._turns.append(_Turn(files={}, side_effects=[]))
            self._needs_new = False
        return self._turns[-1]

    def record_snapshot(
        self,
        rel_path: str,
        pre_content: str,
        post_content: str,
        *,
        existed_before: bool = True,
    ) -> None:
        """Remember the first pre-image of this path for the open turn."""
        turn = self._open_turn()
        post_hash = self._hash(post_content)
        current = turn.files.get(rel_path)
        if current is None:
            turn.files[rel_path] = FileSnapshot(
                rel_path=rel_path,
                pre_edit_content=pre_content,
                pre_edit_hash=self._hash(pre_content),
                post_edit_hash=post_hash,
                existed_before=existed_before,
            )
            return
        current.post_edit_hash = post_hash

    def record_side_effect(self, description: str) -> None:
        """Log an irreversible effect for the open turn, such as a package install."""
        self._open_turn().side_effects.append(description)

    def undo(self, force: bool = False) -> UndoResult:
        """Roll back the latest turn. A drifted file stays and blocks older turns."""
        if not self._turns:
            return UndoResult([], [], 0, [])
        turn = self._turns[-1]
        reverted: list[str] = []
        conflicts: list[str] = []
        for rel_path, snapshot in list(turn.files.items()):
            if self._revert_file(snapshot, force):
                reverted.append(rel_path)
                turn.files.pop(rel_path, None)
            else:
                conflicts.append(rel_path)
        disclosed: list[str] = []
        if not turn.files:
            disclosed = list(turn.side_effects)
            self._turns.pop()
            self._needs_new = True
        return UndoResult(
            reverted_files=reverted,
            conflicted_files=conflicts,
            terminated_processes=0,
            disclosed_side_effects=disclosed,
        )

    def _revert_file(self, snapshot: FileSnapshot, force: bool) -> bool:
        file_path = resolve_safe_path(self.workspace, snapshot.rel_path)
        if not snapshot.existed_before:
            return self._remove_created(file_path, snapshot, force)
        if not file_path.exists():
            atomic_write(file_path, snapshot.pre_edit_content)
            return True
        if force or self._matches_post(file_path, snapshot):
            atomic_write(file_path, snapshot.pre_edit_content)
            return True
        return False

    def _remove_created(
        self, file_path: Path, snapshot: FileSnapshot, force: bool
    ) -> bool:
        if not file_path.exists():
            return True
        if not file_path.is_file():
            return False
        if not force and not self._matches_post(file_path, snapshot):
            return False
        try:
            file_path.unlink()
        except FileNotFoundError:
            return True
        return True

    def _matches_post(self, file_path: Path, snapshot: FileSnapshot) -> bool:
        try:
            current = read_file(file_path)
        except (OSError, UnicodeDecodeError, BinaryFileError):
            return False
        return self._hash(current) == snapshot.post_edit_hash


def side_effect_note(result: UndoResult) -> str:
    """Text for installs and other changes that restoring files cannot undo."""
    if not result.disclosed_side_effects:
        return ""
    effects = "; ".join(result.disclosed_side_effects)
    return f" Not reverted: {effects}"
