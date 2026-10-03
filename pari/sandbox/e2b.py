"""PARI Layer 0: Cloud E2B Firecracker Sandbox Runner.

Architectural Purpose:
    Satisfies cloud microVM sandboxing using E2B Firecracker hardware KVM microVMs.
    Bypasses weeks of custom hypervisor / vsock plumbing while guaranteeing full
    kernel-level hardware virtualization for remote evaluation and cloud runs.
"""

import os
import time
from pathlib import Path
from typing import Dict, Optional

from pari.sandbox.base import SandboxLimits, SandboxResult, SandboxRunner


class E2BCloudSandboxRunner(SandboxRunner):
    """Executes commands inside an ephemeral E2B Firecracker Cloud microVM."""

    def __init__(self, workspace: Path, limits: Optional[SandboxLimits] = None, api_key: Optional[str] = None):
        super().__init__(workspace, limits)
        self.api_key = api_key or os.environ.get("E2B_API_KEY")
        self._sandbox_instance = None

    def _ensure_sandbox(self):
        if self._sandbox_instance is None:
            try:
                from e2b import Sandbox
                self._sandbox_instance = Sandbox(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("e2b package required for cloud sandbox. Install with: pip install pari[cloud]")

    def run_command(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        self._ensure_sandbox()
        start_time = time.time()
        timeout_val = timeout if timeout is not None else self.limits.timeout_seconds

        try:
            execution = self._sandbox_instance.commands.run(command, envs=env, timeout=timeout_val)
            exit_code = execution.exit_code
            stdout = execution.stdout
            stderr = execution.stderr
            timed_out = False
        except Exception as e:
            exit_code = -1
            stdout = ""
            stderr = str(e)
            timed_out = "timeout" in str(e).lower()

        duration = time.time() - start_time
        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            timed_out=timed_out,
        )

    def cleanup(self) -> None:
        if self._sandbox_instance:
            try:
                self._sandbox_instance.close()
            except Exception:
                pass
            self._sandbox_instance = None
