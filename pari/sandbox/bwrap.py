"""PARI Layer 0: Linux / WSL2 Bubblewrap Sandbox Runner.

Architectural Purpose:
    Harvested from Codex codex-bwrap.
    Provides sub-5ms unprivileged user namespace isolation (zero root required).
    Mounts root / as read-only, workspace as read-write, masks ~/.ssh, ~/.gnupg, and
    drops network namespaces when network isolation is requested.

Kernel Namespaces:
    - CLONE_NEWUSER, CLONE_NEWNS, CLONE_NEWPID, CLONE_NEWIPC, CLONE_NEWUTS.
    - Die-with-parent via bwrap --die-with-parent flag.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from pari.sandbox.base import SandboxLimits, SandboxResult, SandboxRunner


class BwrapSandboxRunner(SandboxRunner):
    """Runs commands in an unprivileged Linux Bubblewrap (bwrap) sandbox."""

    def __init__(self, workspace: Path, limits: Optional[SandboxLimits] = None):
        super().__init__(workspace, limits)
        self.bwrap_bin = shutil.which("bwrap")
        if not self.bwrap_bin:
            raise RuntimeError("bubblewrap ('bwrap') is not installed on this system.")

    def _build_bwrap_args(self) -> List[str]:
        args = [
            self.bwrap_bin,
            "--die-with-parent",
            "--ro-bind", "/", "/",
            "--bind", str(self.workspace), str(self.workspace),
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--chdir", str(self.workspace),
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
        ]

        # Mask sensitive user directories
        home = Path.home()
        for sensitive in [".ssh", ".gnupg", ".aws", ".config/gh"]:
            target = home / sensitive
            if target.exists():
                args.extend(["--tmpfs", str(target)])

        if not self.limits.allow_network:
            args.append("--unshare-net")

        return args

    def run_command(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        timeout_val = timeout if timeout is not None else self.limits.timeout_seconds
        bwrap_cmd = self._build_bwrap_args()
        bwrap_cmd.extend(["--", "/bin/bash", "-c", command])

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        start_time = time.time()
        timed_out = False

        try:
            proc = subprocess.Popen(
                bwrap_cmd,
                cwd=str(self.workspace),
                env=merged_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = proc.communicate(timeout=timeout_val)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            stdout, stderr = proc.communicate()
            exit_code = -1

        duration = time.time() - start_time
        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            timed_out=timed_out,
        )

    def cleanup(self) -> None:
        pass
