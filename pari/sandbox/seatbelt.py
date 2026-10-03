"""PARI Layer 0: macOS Apple Seatbelt Sandbox Runner.

Architectural Purpose:
    Uses macOS sandbox-exec with an explicit TinyScheme profile.
    Confines filesystem write operations strictly to the workspace directory.
    Note: Expands explicit user home path since Seatbelt TinyScheme does not expand tilde (~).
"""

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

from pari.sandbox.base import SandboxLimits, SandboxResult, SandboxRunner


class MacOSSeatbeltSandboxRunner(SandboxRunner):
    """Runs commands in an Apple Seatbelt sandbox via sandbox-exec."""

    def __init__(self, workspace: Path, limits: Optional[SandboxLimits] = None):
        super().__init__(workspace, limits)
        self.sandbox_exec = shutil.which("sandbox-exec")
        if not self.sandbox_exec:
            raise RuntimeError("sandbox-exec is not available on this macOS system.")

    def _generate_profile(self) -> str:
        canonical_ws = str(self.workspace)
        user_home = str(Path.home())
        
        return f"""(version 1)
(deny default)
(allow process-fork)
(allow process-exec)
(allow sysctl-read)
(allow file-read*)
(allow file-write* (subpath "{canonical_ws}"))
(allow file-write* (subpath "/private/tmp"))
(allow file-write* (subpath "/tmp"))
(deny file-read* (subpath "{user_home}/.ssh"))
(deny file-read* (subpath "{user_home}/.gnupg"))
(deny file-read* (subpath "{user_home}/.aws"))
"""

    def run_command(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        timeout_val = timeout if timeout is not None else self.limits.timeout_seconds
        profile = self._generate_profile()

        with tempfile.NamedTemporaryFile("w", suffix=".sb", delete=False) as f:
            f.write(profile)
            profile_path = f.name

        start_time = time.time()
        timed_out = False
        try:
            cmd = [self.sandbox_exec, "-f", profile_path, "/bin/bash", "-c", command]
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.workspace),
                env=env or os.environ.copy(),
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
        finally:
            if os.path.exists(profile_path):
                os.unlink(profile_path)

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
