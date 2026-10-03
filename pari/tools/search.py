"""PARI Tools: Codebase Search and Discovery Tools.

Routes globbing and text grep queries through Layer 3 intelligence search.
"""

from pathlib import Path
from typing import Any, Dict, List
from pari.tools.base import Tool, ToolDefinition
from pari.search import find_files, grep_search


class FindFilesTool(Tool):
    """Finds files matching glob patterns while respecting ignore rules."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_files",
            description="Find files in the workspace matching a glob pattern (e.g. '*.py').",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (default: '*')."},
                    "max_results": {"type": "integer", "description": "Max files to return (default: 50)."},
                },
            },
        )

    async def execute(self, pattern: str = "*", max_results: int = 50) -> List[str]:
        return find_files(self.workspace, pattern=pattern, max_results=max_results)


class GrepTool(Tool):
    """Searches workspace files for regex or substring pattern matches."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="grep_search",
            description="Search file contents for substring or regex matches.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text or regex search query."},
                    "max_matches": {"type": "integer", "description": "Max matching lines (default: 50)."},
                },
                "required": ["query"],
            },
        )

    async def execute(self, query: str, max_matches: int = 50) -> List[Dict[str, Any]]:
        matches = grep_search(self.workspace, query, max_matches=max_matches)
        return [
            {
                "file": m.file_path,
                "line": m.line_number,
                "content": m.line_content,
            }
            for m in matches
        ]
