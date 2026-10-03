"""PARI Tools: Filesystem and Editing Tools.

Integrates Layer 6 safe path resolution and atomic writes with Layer 5 edit cascade.
"""

from pathlib import Path
from typing import Any, Dict
from pari.tools.base import Tool, ToolDefinition
from pari.fs.path import resolve_safe_path
from pari.fs.atomic import atomic_write, read_file
from pari.edit.cascade import EditCascade
from pari.edit.diff import generate_unified_diff


class ReadFileTool(Tool):
    """Safely reads file contents within workspace boundary."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_file",
            description="Read the entire text content of a file within the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file."},
                },
                "required": ["path"],
            },
        )

    async def execute(self, path: str) -> str:
        safe_path = resolve_safe_path(self.workspace, path)
        if not safe_path.exists():
            raise FileNotFoundError(f"File '{path}' does not exist.")
        return read_file(safe_path)



class WriteFileTool(Tool):
    """Safely and atomically writes or creates a file."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write_file",
            description="Atomically write new content to a file in the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file."},
                    "content": {"type": "string", "description": "File text content."},
                },
                "required": ["path", "content"],
            },
        )

    async def execute(self, path: str, content: str) -> str:
        safe_path = resolve_safe_path(self.workspace, path)
        atomic_write(safe_path, content)
        return f"Successfully wrote {len(content)} characters to '{path}'."


class EditFileTool(Tool):
    """Safely edits an existing file using multi-tier fuzzy search/replace cascade."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.cascade = EditCascade(allow_fallbacks=True)

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="edit_file",
            description="Replace an exact or unique block of code with new content.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file."},
                    "search": {"type": "string", "description": "Target block to replace."},
                    "replace": {"type": "string", "description": "New replacement content."},
                },
                "required": ["path", "search", "replace"],
            },
        )

    async def execute(self, path: str, search: str, replace: str) -> Dict[str, Any]:
        safe_path = resolve_safe_path(self.workspace, path)

        if not safe_path.exists():
            raise FileNotFoundError(f"File '{path}' does not exist.")

        original = read_file(safe_path)
        new_content, tier = self.cascade.apply(original, search, replace)
        diff = generate_unified_diff(original, new_content, filename=path)
        atomic_write(safe_path, new_content)

        return {
            "status": "success",
            "tier_used": tier,
            "diff": diff,
        }
