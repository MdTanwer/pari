"""PARI Tools: Sandboxed Bash Execution.

Routes command execution through Layer 0 sandbox (Bubblewrap / Seatbelt / Process Group)
and spools large outputs through Layer 7 ManagedOutputSpooler.
"""

from pathlib import Path
from typing import Any

from pari.tools.base import Tool, ToolDefinition


class BashTool(Tool):
    """Executes a shell command inside the kernel sandbox."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def definition(self) -> ToolDefinition:
        raise NotImplementedError

    async def execute(self, command: str, timeout: float = 30.0) -> dict[str, Any]:
        """Execute command inside sandbox with output spooling."""
        raise NotImplementedError
