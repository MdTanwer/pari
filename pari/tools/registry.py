"""PARI Tools: Central Registry and Dispatcher.

Manages tool registration, schema exportation for model prompts, and dispatch execution.
"""

from pathlib import Path
from typing import Any

from pari.tools.base import Tool
from pari.tools.bash import BashTool
from pari.tools.fs import EditFileTool, ReadFileTool, WriteFileTool
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


def get_default_registry(workspace: Path) -> ToolRegistry:
    """Instantiate and register the standard PARI tool suite for a given workspace."""
    registry = ToolRegistry()
    for tool in (
        BashTool(workspace),
        ReadFileTool(workspace),
        WriteFileTool(workspace),
        EditFileTool(workspace),
        FindFilesTool(workspace),
        GrepTool(workspace),
    ):
        registry.register(tool)
    return registry
