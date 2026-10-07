"""PARI Tools: Filesystem and Editing Tools.

Integrates Layer 6 safe path resolution and atomic writes with Layer 5 exact edit.
"""

from pathlib import Path
from typing import Any

from pari.edit.exact import apply_exact_edit
from pari.fs.atomic import atomic_write, read_file
from pari.fs.path import resolve_safe_path
from pari.tools.base import Tool, ToolDefinition


class ReadFileTool(Tool):
    """Safely reads file contents within workspace boundary."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

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

    async def execute(self, path: str) -> str:
        """Read target file."""
        target = resolve_safe_path(self.workspace, path)
        return read_file(target)


class WriteFileTool(Tool):
    """Safely and atomically writes or creates a file."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

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
        """Atomically write file."""
        target = resolve_safe_path(self.workspace, path)
        atomic_write(target, content)
        return f"Successfully wrote {path}"


class EditFileTool(Tool):
    """Safely edits an existing file using exact search/replace."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

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
        """Apply an exact edit. The file is unchanged when the match is not unique."""
        target = resolve_safe_path(self.workspace, path)
        original = read_file(target)
        updated = apply_exact_edit(original, search, replace, filename=path)
        atomic_write(target, updated)
        return {"status": "success", "path": path}
