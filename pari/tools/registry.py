"""PARI Tools: Central Registry and Dispatcher.

Manages tool registration, schema exportation for model prompts, and dispatch execution.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from pari.tools.base import Tool


class ToolRegistry:
    """Registry maintaining active agent tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Register a new tool instance."""
        raise NotImplementedError

    def get(self, name: str) -> Optional[Tool]:
        """Look up tool by name."""
        raise NotImplementedError

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Return list of JSON schemas for all registered tools."""
        raise NotImplementedError

    async def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Dispatch tool execution by name with given arguments."""
        raise NotImplementedError


def get_default_registry(workspace: Path) -> ToolRegistry:
    """Instantiate and register the standard PARI tool suite for a given workspace."""
    raise NotImplementedError
