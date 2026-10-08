"""PARI Tools: Central Registry and Dispatcher.

Manages tool registration, schema exportation for model prompts, and dispatch execution.
"""

from pathlib import Path
from typing import Any

from pari.fs.queue import FileMutationQueue
from pari.output.spooler import ManagedOutputSpooler
from pari.tools.base import Tool
from pari.tools.bash import BashTool
from pari.tools.fs import EditFileTool, ReadFileTool, WriteFileTool
from pari.tools.output_reader import ReadToolOutputTool
from pari.tools.search import FindFilesTool, GrepTool


class ToolRegistry:
    """Registry maintaining active agent tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a new tool instance."""
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> Tool | None:
        """Look up tool by name."""
        return self._tools.get(name)

    def get_schemas(self) -> list[dict[str, Any]]:
        """Return list of JSON schemas for all registered tools."""
        return [tool.definition.to_schema() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch tool execution by name with given arguments."""
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return await tool.execute(**arguments)


def get_default_registry(workspace: Path, edit_fallback: str = "none") -> ToolRegistry:
    """Instantiate and register the standard PARI tool suite for a given workspace.

    edit_fallback is ``none`` or ``cascade``. Exact replacement stays the default.
    """
    registry = ToolRegistry()
    # One queue so read, write, and edit of the same file share a lock.
    queue = FileMutationQueue(workspace)
    spool_dir = workspace / ".pari" / "tool-outputs"
    for tool in (
        BashTool(workspace, spooler=ManagedOutputSpooler(spool_dir)),
        ReadFileTool(workspace, queue=queue),
        WriteFileTool(workspace, queue=queue),
        EditFileTool(workspace, queue=queue, edit_fallback=edit_fallback),
        FindFilesTool(workspace),
        GrepTool(workspace),
        ReadToolOutputTool(spool_dir),
    ):
        registry.register(tool)
    return registry
