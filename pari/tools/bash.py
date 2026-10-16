"""PARI Tools: Sandboxed Bash Execution.

Routes command execution through Layer 0 sandbox (Bubblewrap) and returns
the capped stdout and stderr from that run.
"""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pari.output.spooler import ManagedOutputSpooler
from pari.sandbox.base import SandboxLimits
from pari.sandbox.dispatcher import get_sandbox_runner
from pari.tools.base import Tool, ToolDefinition


class BashTool(Tool):
    """Executes a shell command inside the kernel sandbox."""

    def __init__(
        self,
        workspace: Path,
        spooler: ManagedOutputSpooler | None = None,
        sandbox_mode: str | None = None,
    ):
        self.workspace = workspace
        self.sandbox_mode = sandbox_mode
        spool_dir = workspace / ".pari" / "tool-outputs"
        self.spooler = spooler or ManagedOutputSpooler(spool_dir)
        # The TUI sets this so command output prints while the process runs.
        self.on_output: Callable[[str, str], None] | None = None

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
        # Imported here because this module is loaded while the agent package
        # is still initializing.
        from pari.agent.guards import DAEMON_IDLE_SECONDS

        # A requested timeout shorter than 10s is the whole wait.
        # A longer one still yields at 10s so a server cannot hold the turn.
        idle = DAEMON_IDLE_SECONDS if timeout > DAEMON_IDLE_SECONDS else None
        limits = SandboxLimits(timeout_seconds=timeout, daemon_idle_seconds=idle)
        runner = get_sandbox_runner(
            self.workspace, limits=limits, force_mode=self.sandbox_mode
        )
        result = runner.run_command(command, timeout=timeout, on_output=self.on_output)
        raw = result.stdout
        if result.stderr:
            raw += result.stderr
        # The prompt sees the bounded view. The full log stays in the sidecar.
        spooled = self.spooler.spool(raw, command_tag="bash")
        return {
            "exit_code": result.exit_code,
            "output": spooled.context_text,
            "timed_out": result.timed_out,
            "timeout": timeout,
            "idle_seconds": DAEMON_IDLE_SECONDS if result.daemon else timeout,
            "truncated": spooled.was_truncated,
            "sidecar_path": str(spooled.sidecar_path),
        }
