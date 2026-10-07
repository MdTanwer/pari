"""PARI Tools: Codebase Search and Discovery Tools.

Routes globbing and text grep queries through Layer 3 intelligence search.
"""

from pathlib import Path
from typing import Any

from pari.intelligence.search import find_files, grep_search
from pari.tools.base import Tool, ToolDefinition


class FindFilesTool(Tool):
    """Finds files matching glob patterns while respecting ignore rules."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_files",
            description="List workspace files matching a glob pattern.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern. Defaults to all files.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of paths to return.",
                    },
                },
                "required": [],
            },
        )

    async def execute(self, pattern: str = "*", max_results: int = 50) -> list[str]:
        """Find files matching pattern."""
        return find_files(self.workspace, pattern, max_results)


class GrepTool(Tool):
    """Searches workspace files for regex or substring pattern matches."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="grep_search",
            description="Search file contents for a substring or regular expression.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text or regular expression to find.",
                    },
                    "max_matches": {
                        "type": "integer",
                        "description": "Maximum number of matching lines.",
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, query: str, max_matches: int = 50) -> list[dict[str, Any]]:
        """Search file contents for pattern."""
        return grep_search(self.workspace, query, max_matches=max_matches)
