"""PARI Tools: Sandboxed Bash Execution.

Routes command execution through Layer 0 sandbox (Bubblewrap) and returns
the capped stdout and stderr from that run.
"""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from pari.output.spooler import ManagedOutputSpooler
from pari.permissions.credentials import granted_env
from pari.permissions.policy import Decision, PermissionPolicy, normalize_choice
from pari.sandbox.base import SandboxLimits, SandboxRunner
from pari.sandbox.dispatcher import get_sandbox_runner
from pari.tools.base import Tool, ToolDefinition


# A model can ask for timeout=10**9. The sandbox wait never exceeds this.
MAX_TOOL_TIMEOUT = 600.0


class BashTool(Tool):
    """Executes a shell command inside the kernel sandbox."""

    def __init__(
        self,
        workspace: Path,
        spooler: ManagedOutputSpooler | None = None,
        sandbox_mode: str | None = None,
        permission_home: Path | None = None,
    ):
        self.workspace = workspace
        self.sandbox_mode = sandbox_mode
        self.permission_home = permission_home
        spool_dir = workspace / ".pari" / "tool-outputs"
        self.spooler = spooler or ManagedOutputSpooler(spool_dir)
        self._runner: SandboxRunner | None = None
        # The TUI sets this so command output prints while the process runs.
        self.on_output: Callable[[str, str], None] | None = None
        # The TUI sets this so a widening stops for once / this repo / no.
        self.ask_permission: Callable[[Decision], Awaitable[str]] | None = None

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
                        "description": (
                            "Timeout in seconds. Values above 600 are capped."
                        ),
                    },
                },
                "required": ["command"],
            },
        )

    async def execute(self, command: str, timeout: float = 30.0) -> dict[str, Any]:
        """Execute command inside sandbox with output capping."""
        # Imported here because this module is loaded while the agent package
        # is still initializing.
        from pari.agent.guards import DAEMON_IDLE_SECONDS

        timeout = min(float(timeout), MAX_TOOL_TIMEOUT)
        # A requested timeout shorter than 10s is the whole wait.
        # A longer one still yields at 10s so a server cannot hold the turn.
        idle = DAEMON_IDLE_SECONDS if timeout > DAEMON_IDLE_SECONDS else None
        policy = PermissionPolicy.load(self.workspace, home=self.permission_home)
        decision = policy.decide("bash", command)
        if decision.action == "deny":
            return _refused(decision.message, timeout)
        if decision.action == "ask":
            choice = await self._choose(decision)
            if choice == "repo":
                policy.save_project_rule(decision.save_line)
            elif choice != "once":
                return _refused(decision.message, timeout)
        env = granted_env(decision.grants, self.workspace)
        if decision.grants.github_token and "GH_TOKEN" not in env:
            return _refused("GitHub token was not available on this machine.", timeout)
        limits = decision.sandbox_limits(timeout, idle, granted_env=env)
        return await asyncio.to_thread(self._run, command, timeout, limits)

    async def _choose(self, decision: Decision) -> str:
        """Ask the user. No prompt means no."""
        ask = self.ask_permission
        if ask is None:
            return "no"
        try:
            choice = await ask(decision)
        except Exception:
            # A broken prompt must not start the command.
            return "no"
        return normalize_choice(choice)

    def cleanup(self) -> None:
        """Kill a command still running in this tool and drop its cgroup."""
        runner = self._runner
        if runner is not None:
            runner.cleanup()

    def _command_runner(self, limits: SandboxLimits) -> SandboxRunner:
        """One runner for the life of the tool, so cleanup can see its children."""
        runner = self._runner
        if runner is None:
            runner = get_sandbox_runner(
                self.workspace, limits=limits, force_mode=self.sandbox_mode
            )
            self._runner = runner
        else:
            runner.limits = limits
        return runner

    def _run(
        self, command: str, timeout: float, limits: SandboxLimits
    ) -> dict[str, Any]:
        from pari.agent.guards import DAEMON_IDLE_SECONDS

        runner = self._command_runner(limits)
        try:
            result = runner.run_command(
                command, timeout=timeout, on_output=self.on_output
            )
        except KeyboardInterrupt:
            runner.cleanup()
            raise
        raw = result.stdout
        if result.stderr:
            raw += result.stderr
        # The prompt sees the bounded view. A sidecar exists only past the budget.
        spooled = self.spooler.spool(raw, command_tag="bash")
        sidecar = "" if spooled.sidecar_path is None else str(spooled.sidecar_path)
        return {
            "exit_code": result.exit_code,
            "output": spooled.context_text,
            "timed_out": result.timed_out,
            "timeout": timeout,
            "idle_seconds": DAEMON_IDLE_SECONDS if result.daemon else timeout,
            "truncated": spooled.was_truncated,
            "sidecar_path": sidecar,
        }


def _refused(message: str, timeout: float) -> dict[str, Any]:
    """A command that did not start. The model sees why."""
    if message.startswith(("Permission denied", "This session")):
        output = message
    else:
        output = f"Permission denied. {message}"
    return {
        "exit_code": 1,
        "output": output,
        "timed_out": False,
        "timeout": timeout,
        "idle_seconds": timeout,
        "truncated": False,
        "sidecar_path": "",
        "denied": True,
    }
