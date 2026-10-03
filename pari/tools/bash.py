"""PARI Tools: Sandboxed Bash Execution.

Routes command execution through Layer 0 sandbox (Bubblewrap / Seatbelt / Process Group)
and spools large outputs through Layer 7 ManagedOutputSpooler.
"""

from pathlib import Path
from typing import Any, Dict
from pari.tools.base import Tool, ToolDefinition
from pari.sandbox.dispatcher import get_sandbox_runner
from pari.output.spooler import ManagedOutputSpooler


class BashTool(Tool):
    """Executes a shell command inside the kernel sandbox."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sandbox = get_sandbox_runner(self.workspace)
        self.spooler = ManagedOutputSpooler()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="bash",
            description="Execute a shell command inside the workspace sandbox.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command line to execute.",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Optional timeout in seconds (default: 30s).",
                    },
                },
                "required": ["command"],
            },
        )

    async def execute(self, command: str, timeout: float = 30.0) -> Dict[str, Any]:
        result = self.sandbox.run_command(command, timeout=timeout)
        combined_output = result.stdout
        if result.stderr:
            combined_output += ("\nSTDERR:\n" + result.stderr) if combined_output else result.stderr

        spool = self.spooler.spool(combined_output, command_tag="bash")

        return {
            "exit_code": result.exit_code,
            "output": spool.context_text,
            "timed_out": result.timed_out,
            "truncated": spool.was_truncated,
            "spool_file": str(spool.sidecar_path) if spool.was_truncated else None,
        }
