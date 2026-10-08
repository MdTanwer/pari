"""PARI Tools: Filesystem and Editing Tools.

Integrates Layer 6 safe path resolution and atomic writes with Layer 5 exact edit.
"""

from pathlib import Path
from typing import Any

from pari.edit.exact import apply_exact_edit
from pari.fs.atomic import atomic_write, read_file
from pari.fs.path import resolve_safe_path
from pari.fs.queue import FileMutationQueue
from pari.tools.base import Tool, ToolDefinition


class ReadFileTool(Tool):
    """Safely reads file contents within workspace boundary."""

    def __init__(self, workspace: Path, queue: FileMutationQueue | None = None):
        self.workspace = workspace
        self.queue = queue or FileMutationQueue(workspace)

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description="Read a text file inside the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative file path.",
                    }
                },
                "required": ["path"],
            },
        )

    async def execute(
        self, path: str, offset: int = 1, limit: int | None = None
    ) -> str:
        """Read target file, optionally a line window.

        offset is 1-based. The file lock is held so a read cannot overlap a
        write of the same inode.
        """
        target = resolve_safe_path(self.workspace, path)
        lock = await self.queue.get_lock(target)
        async with lock:
            text = read_file(target)
        if offset <= 1 and limit is None:
            return text
        lines = text.splitlines(keepends=True)
        start = max(offset, 1) - 1
        end = None if limit is None else start + limit
        return "".join(lines[start:end])


class WriteFileTool(Tool):
    """Safely and atomically writes or creates a file."""

    def __init__(self, workspace: Path, queue: FileMutationQueue | None = None):
        self.workspace = workspace
        self.queue = queue or FileMutationQueue(workspace)

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
        await self.queue.write(Path(path), content)
        return f"Successfully wrote {path}"


class EditFileTool(Tool):
    """Safely edits an existing file using exact search/replace."""

    def __init__(self, workspace: Path, queue: FileMutationQueue | None = None):
        self.workspace = workspace
        self.queue = queue or FileMutationQueue(workspace)

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
        """
        target = resolve_safe_path(self.workspace, path)
        lock = await self.queue.get_lock(target)
        async with lock:
            original = read_file(target)
            updated = apply_exact_edit(original, search, replace, filename=path)
            atomic_write(target, updated)
        return {"status": "success", "path": path}
