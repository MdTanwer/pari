"""PARI Tools: Sandboxed Bash Execution.

Routes command execution through Layer 0 sandbox (Bubblewrap) and returns
the capped stdout and stderr from that run.
"""

import asyncio
from pathlib import Path
from typing import Any

from pari.sandbox.base import SandboxLimits
from pari.sandbox.dispatcher import get_sandbox_runner
from pari.tools.base import Tool, ToolDefinition


class BashTool(Tool):
    """Executes a shell command inside the kernel sandbox."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="bash",
            description="Run a shell command inside the workspace sandbox.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute.",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Timeout in seconds.",
                    },
                },
                "required": ["command"],
            },
        )

    async def execute(self, command: str, timeout: float = 30.0) -> dict[str, Any]:
        """Execute command inside sandbox with output capping."""
        return await asyncio.to_thread(self._run, command, timeout)

    def _run(self, command: str, timeout: float) -> dict[str, Any]:
        limits = SandboxLimits(timeout_seconds=timeout)
        runner = get_sandbox_runner(self.workspace, limits=limits)
        result = runner.run_command(command, timeout=timeout)
        output = result.stdout
        if result.stderr:
            output += result.stderr
        return {
            "exit_code": result.exit_code,
            "output": output,
            "timed_out": result.timed_out,
        }
