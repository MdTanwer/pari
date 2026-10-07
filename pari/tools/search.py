"""PARI Tools: Codebase Search and Discovery Tools.

Routes globbing and text grep queries through Layer 3 intelligence search.
"""

from pathlib import Path
from typing import Any

from pari.tools.base import Tool, ToolDefinition


class FindFilesTool(Tool):
    """Finds files matching glob patterns while respecting ignore rules."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def definition(self) -> ToolDefinition:
        raise NotImplementedError

    async def execute(self, pattern: str = "*", max_results: int = 50) -> list[str]:
        """Find files matching pattern."""
        raise NotImplementedError


class GrepTool(Tool):
    """Searches workspace files for regex or substring pattern matches."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def definition(self) -> ToolDefinition:
        raise NotImplementedError

    async def execute(self, query: str, max_matches: int = 50) -> list[dict[str, Any]]:
        """Search file contents for pattern."""
        raise NotImplementedError
