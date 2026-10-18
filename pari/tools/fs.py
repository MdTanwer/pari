"""PARI Tools: Filesystem and Editing Tools.

Integrates Layer 6 safe path resolution and atomic writes with Layer 5 exact edit.
"""

from pathlib import Path
from typing import Any

from pari.edit.cascade import EditCascade
from pari.edit.exact import apply_exact_edit
from pari.fs.atomic import BinaryFileError, atomic_write, read_file
from pari.fs.path import resolve_safe_path, resolve_writable_path
from pari.fs.queue import FileMutationQueue
from pari.output.spooler import ManagedOutputSpooler
from pari.permissions.policy import PermissionPolicy
from pari.tools.base import Tool, ToolDefinition


# A default read stays inside this budget. Larger files are spooled.
_READ_MAX_BYTES = 100 * 1024
_READ_MAX_LINES = 2000


class ReadFileTool(Tool):
    """Safely reads file contents within workspace boundary."""

    def __init__(self, workspace: Path, queue: FileMutationQueue):
        self.workspace = workspace
        self.queue = queue
        self.spooler = ManagedOutputSpooler(
            workspace / ".pari" / "tool-outputs",
            max_bytes=_READ_MAX_BYTES,
            max_lines=_READ_MAX_LINES,
        )

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description=(
                "Read a text file inside the workspace. "
                "A file over 2,000 lines or 100 KB returns a window; "
                "pass offset and limit to read another range."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative file path.",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "1-based line to start from.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to return.",
                    },
                },
                "required": ["path"],
            },
        )

    async def execute(
        self, path: str, offset: int = 1, limit: int | None = None
    ) -> str:
        """Read a text file, or a line window when offset or limit is set.

        offset is 1-based. The file lock is held so a read cannot overlap a
        write of the same inode. A binary file returns a message. A read past
        2,000 lines or 100 KB returns a prefix and a sidecar path.
        """
        target = resolve_safe_path(self.workspace, path)
        lock = await self.queue.get_lock(target)
        async with lock:
            try:
                text = read_file(target)
            except BinaryFileError:
                return f"Binary file: {path}"
        window = _line_window(text, offset, limit)
        return self._bounded(window)

    def _bounded(self, text: str) -> str:
        """Return text that fits the cap, otherwise a prefix plus the sidecar."""
        if not _over_read_cap(text):
            return text
        spooled = self.spooler.spool(text, command_tag="read")
        notice = (
            f"\n... [OMITTED. Full file: {spooled.sidecar_path}] ...\n"
            "File exceeds 2,000 lines or 100 KB. "
            "Use read_file offset and limit for another window."
        )
        # The prefix and the notice together must stay strictly inside the cap.
        budget = _READ_MAX_BYTES - len(notice.encode("utf-8")) - 1
        return f"{_prefix_window(text, max_bytes=budget)}{notice}"


class WriteFileTool(Tool):
    """Safely and atomically writes or creates a file."""

    def __init__(self, workspace: Path, queue: FileMutationQueue):
        self.workspace = workspace
        self.queue = queue

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_file",
            description="Create or overwrite a file inside the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative file path.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file contents to write.",
                    },
                },
                "required": ["path", "content"],
            },
        )

    async def execute(self, path: str, content: str) -> str:
        """Atomically write file while holding its canonical lock."""
        resolve_writable_path(self.workspace, path)
        if _session_read_only(self.workspace):
            return "This session is read-only."
        await self.queue.write(Path(path), content)
        return f"Successfully wrote {path}"


class EditFileTool(Tool):
    """Safely edits an existing file using exact search/replace."""

    def __init__(
        self,
        workspace: Path,
        queue: FileMutationQueue,
        edit_fallback: str = "none",
    ):
        self.workspace = workspace
        self.queue = queue
        # "cascade" is the only fallback. Every other value stays exact.
        self.edit_fallback = edit_fallback

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="edit_file",
            description=(
                "Replace one unique occurrence of search text in a workspace file."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative file path.",
                    },
                    "search": {
                        "type": "string",
                        "description": "Exact text to replace. Must match once.",
                    },
                    "replace": {
                        "type": "string",
                        "description": "Replacement text.",
                    },
                },
                "required": ["path", "search", "replace"],
            },
        )

    async def execute(self, path: str, search: str, replace: str) -> dict[str, Any]:
        """Apply an exact edit under the file lock.

        The lock covers the read and the replace together. A second edit of
        the same file waits, so the two search strings cannot tear the file.
        The file is unchanged when the match is not unique.
        Exact mode also leaves it unchanged when the text is missing.
        Cascade mode may then align whitespace or a close window.
        """
        target = resolve_writable_path(self.workspace, path)
        if _session_read_only(self.workspace):
            return {
                "status": "denied",
                "path": path,
                "error": "This session is read-only.",
            }
        lock = await self.queue.get_lock(target)
        async with lock:
            original = read_file(target)
            updated, tier = self._apply(original, search, replace, path)
            atomic_write(target, updated)
        return {"status": "success", "path": path, "tier": tier}

    def _apply(
        self, original: str, search: str, replace: str, path: str
    ) -> tuple[str, str]:
        if self.edit_fallback == "cascade":
            return EditCascade().apply(original, search, replace, path)
        updated = apply_exact_edit(original, search, replace, filename=path)
        return updated, "exact"


def _session_read_only(workspace: Path) -> bool:
    return PermissionPolicy.load(workspace).read_only


def _line_window(text: str, offset: int, limit: int | None) -> str:
    """Slice lines. offset is 1-based. No limit keeps the tail of the file."""
    if offset <= 1 and limit is None:
        return text
    lines = text.splitlines(keepends=True)
    start = max(offset, 1) - 1
    end = None if limit is None else start + max(limit, 0)
    return "".join(lines[start:end])


def _over_read_cap(text: str) -> bool:
    if len(text.encode("utf-8")) > _READ_MAX_BYTES:
        return True
    return len(text.splitlines()) > _READ_MAX_LINES


def _prefix_window(text: str, max_bytes: int = _READ_MAX_BYTES) -> str:
    """Keep the leading lines that fit in both the byte cap and the line cap."""
    raw = text.encode("utf-8")
    if len(raw) > max_bytes:
        text = raw[:max_bytes].decode("utf-8", errors="ignore")
    lines = text.splitlines(keepends=True)
    if len(lines) <= _READ_MAX_LINES:
        return text
    return "".join(lines[:_READ_MAX_LINES])
