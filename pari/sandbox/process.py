"""PARI Layer 0: Process Group Supervisor & Fallback Runner.

Architectural Purpose:
    Closes Codex F5 (Orphaned exec-server processes) and provides the supervised
    fallback runner when kernel sandbox utilities (bwrap/seatbelt) are absent.

Features:
    - Creates independent process groups using os.setsid() so child process trees
      can be terminated cleanly as a unit (killpg).
    - Sets PR_SET_PDEATHSIG on Linux so child processes terminate if the parent crashes.
    - Prevents zombie process accumulation via signal handling and reaping.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from pari.sandbox.base import SandboxLimits, SandboxResult, SandboxRunner


def _preexec_die_with_parent():
    """Configure child process to establish its own process group and die if parent dies."""
    # Create new session and process group
    os.setsid()
    
    # On Linux, request SIGKILL if parent process terminates
    if sys.platform == "linux":
        try:
            import ctypes
            libc = ctypes.CDLL("libc.so.6")
            PR_SET_PDEATHSIG = 1
            libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL)
        except Exception:
            pass


class SupervisedProcessRunner(SandboxRunner):
    """Supervised process runner using process-group tracking and path-guard boundaries."""

    def __init__(self, workspace: Path, limits: Optional[SandboxLimits] = None):
        super().__init__(workspace, limits)
        self.active_pids: List[int] = []

    def run_command(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        timeout_val = timeout if timeout is not None else self.limits.timeout_seconds
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        start_time = time.time()
        timed_out = False

        try:
            proc = subprocess.Popen(
                ["/bin/bash", "-c", command],
                cwd=str(self.workspace),
                env=merged_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=_preexec_die_with_parent if sys.platform != "win32" else None,
                text=True,
            )
            self.active_pids.append(proc.pid)

            stdout, stderr = proc.communicate(timeout=timeout_val)
            exit_code = proc.returncode

        except subprocess.TimeoutExpired:
            timed_out = True
            # Terminate the entire process group
            try:
                if sys.platform != "win32":
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                else:
                    proc.kill()
            except ProcessLookupError:
                pass
            stdout, stderr = proc.communicate()
            exit_code = -1
        finally:
            if proc.pid in self.active_pids:
                self.active_pids.remove(proc.pid)

        duration = time.time() - start_time
        
        # Enforce output length limit
        max_bytes = self.limits.max_output_bytes
        truncated = False
        if len(stdout.encode("utf-8")) > max_bytes:
            stdout = stdout[:max_bytes] + "\n... [TRUNCATED BY PARI OUTPUT HYGIENE] ..."
            truncated = True

        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            timed_out=timed_out,
            truncated=truncated,
        )

    def cleanup(self) -> None:
        """Kill all recorded active process groups."""
        for pid in list(self.active_pids):
            try:
                if sys.platform != "win32":
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                else:
                    os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
        self.active_pids.clear()
