"""PARI Layer 0: Process Group Supervisor & Fallback Runner.

Architectural Purpose:
    Closes Codex F5 (Orphaned exec-server processes) and provides the supervised
    fallback runner when kernel sandbox utilities (bwrap/seatbelt) are absent.

Features:
    - Creates independent process groups using os.setsid() so child process trees
      can be terminated cleanly as a unit (killpg).
    - Sets PR_SET_PDEATHSIG on Linux so child processes terminate if the parent crashes.
    - Prevents zombie process accumulation via signal handling and reaping.

This runner does not create a mount namespace. Prefer BwrapSandboxRunner on Linux.
"""

import os
from pathlib import Path

from pari.sandbox.base import (
    SANDBOX_PATH,
    SandboxLimits,
    SandboxResult,
    SandboxRunner,
    scrub_env,
)


class SupervisedProcessRunner(SandboxRunner):
    """Supervised process runner using process-group tracking and a workspace cwd."""

    def __init__(self, workspace: Path, limits: SandboxLimits | None = None):
        super().__init__(workspace, limits)

    def run_command(
        self,
        command: str,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> SandboxResult:
        child_env = scrub_env(
            env,
            home=str(self.workspace),
            path=os.environ.get("PATH", SANDBOX_PATH),
        )
        shell = "/bin/sh" if Path("/bin/sh").exists() else "/usr/bin/sh"
        return self._execute(
            [shell, "-c", command],
            cwd=self.workspace,
            env=child_env,
            timeout=timeout if timeout is not None else self.limits.timeout_seconds,
        )

    def cleanup(self) -> None:
        self._cleanup_processes()
