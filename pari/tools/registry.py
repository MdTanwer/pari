"""PARI Tools: Central Registry and Dispatcher.

Manages tool registration, schema exportation for model prompts, and dispatch execution.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from pari.tools.base import Tool, ToolDefinition


class ToolRegistry:
    """Registry maintaining active agent tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [tool.definition.to_schema() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
        tool = self.get(name)
        if not tool:
            raise KeyError(f"Tool '{name}' is not registered.")
        return await tool.execute(**arguments)


def get_default_registry(workspace: Path) -> ToolRegistry:
    """Instantiate and register the standard PARI tool suite for a given workspace."""
    from pari.tools.bash import BashTool
    from pari.tools.fs import ReadFileTool, EditFileTool, WriteFileTool
    from pari.tools.search import GrepTool, FindFilesTool

    registry = ToolRegistry()
    registry.register(BashTool(workspace))
    registry.register(ReadFileTool(workspace))
    registry.register(EditFileTool(workspace))
    registry.register(WriteFileTool(workspace))
    registry.register(GrepTool(workspace))
    registry.register(FindFilesTool(workspace))
    return registry
