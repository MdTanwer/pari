"""PARI Layer 0: Base Sandbox Interface.

Defines the contract for all platform sandbox implementations (Bubblewrap, Seatbelt, E2B, ProcessGroup).
All commands executed by PARI must run through an implementation of SandboxRunner.

Guarantees:
    1. Working directory isolation: Writes restricted to authorized workspace tree.
    2. Die-with-parent lifecycle: Child processes killed when agent process terminates.
    3. Resource bounding: Execution constrained by timeout, max output bytes, and memory.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

_SECRET_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "COOKIE")
_SECRET_ENV_NAMES = {"SSH_AUTH_SOCK", "SSH_AGENT_PID"}


def scrub_env(extra: Optional[Dict[str, str]] = None, *, home: str) -> Dict[str, str]:
    """Build a minimal environment that does not forward host credentials."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
        "HOME": home,
        "TMPDIR": "/tmp",
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    if not extra:
        return env
    for key, value in extra.items():
        if _is_secret_env(key) or "\x00" in key or "\x00" in value:
            continue
        env[key] = value
    return env


def _is_secret_env(name: str) -> bool:
    upper = name.upper()
    if upper in _SECRET_ENV_NAMES:
        return True
    return any(marker in upper for marker in _SECRET_ENV_MARKERS)


@dataclass
class SandboxLimits:
    """Resource constraints for sandboxed command execution.

    Fields:
        timeout_seconds: Maximum allowed wall-clock run duration.
        max_output_bytes: Ceiling for stdout/stderr spooling.
        memory_limit_mb: cgroup ceiling on Linux.
        allow_network: Policy toggle for network interface access.
    """

    timeout_seconds: float = 30.0
    max_output_bytes: int = 50 * 1024
    memory_limit_mb: int = 2048
    allow_network: bool = True


@dataclass
class SandboxResult:
    """Structured result from sandboxed command execution.

    Fields:
        exit_code: Process return code.
        stdout: Standard output string (truncated if exceeding limits).
        stderr: Standard error string.
        duration_seconds: Elapsed execution time.
        timed_out: True if terminated by timeout.
        truncated: True if output exceeded max_output_bytes.
    """

    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    truncated: bool = False


@dataclass
class _StreamCapture:
    stdout: bytearray = field(default_factory=bytearray)
    stderr: bytearray = field(default_factory=bytearray)
    truncated: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


class SandboxRunner(ABC):
    """Abstract base class for all PARI kernel and cloud sandboxes."""

    def __init__(self, workspace: Path, limits: Optional[SandboxLimits] = None):
        self.workspace = Path(workspace).resolve()
        if not self.workspace.is_dir():
            raise NotADirectoryError(f"Workspace is not a directory: {self.workspace}")
        self.limits = limits or SandboxLimits()
        self._active_pgids: set[int] = set()
        self._cgroups: List[Path] = []

    @abstractmethod
    def run_command(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        """Execute a shell command inside the sandbox."""
        raise NotImplementedError

    @abstractmethod
    def cleanup(self) -> None:
        """Terminate any lingering child processes, virtual mounts, or microVM instances."""
        raise NotImplementedError

    def _child_setup(self) -> None:
        """Run in the forked child: new process group, die with parent, memory cap."""
        os.setsid()
        if sys.platform == "linux":
            import ctypes

            libc = ctypes.CDLL(None, use_errno=True)
            libc.prctl(1, signal.SIGKILL)  # PR_SET_PDEATHSIG = 1
            if os.getppid() == 1:
                os._exit(1)
            try:
                import resource

                byte_cap = self.limits.memory_limit_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (byte_cap, byte_cap))
            except (ImportError, OSError, ValueError):
                pass

    def _execute(
        self,
        argv: List[str],
        *,
        cwd: Path,
        env: Dict[str, str],
        timeout: float,
        preexec: Optional[Callable[[], None]] = None,
    ) -> SandboxResult:
        """Run argv with a timeout, an output cap, and process-group teardown."""
        started = time.monotonic()
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=preexec or self._child_setup,
        )
        self._active_pgids.add(proc.pid)
        self._place_in_cgroup(proc.pid)
        capture = _StreamCapture()
        threads = [
            threading.Thread(target=self._drain, args=(proc.stdout, capture, "stdout"), daemon=True),
            threading.Thread(target=self._drain, args=(proc.stderr, capture, "stderr"), daemon=True),
        ]
        for thread in threads:
            thread.start()

        timed_out = False
        deadline = started + timeout
        while proc.poll() is None:
            if capture.truncated or time.monotonic() >= deadline:
                timed_out = not capture.truncated and time.monotonic() >= deadline
                self._kill_group(proc.pid)
                break
            time.sleep(0.01)

        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._kill_group(proc.pid)
            proc.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=1)
        self._active_pgids.discard(proc.pid)

        exit_code = proc.returncode if proc.returncode is not None else 1
        if timed_out:
            exit_code = 124
        stdout_text, stdout_cut = self._decode(bytes(capture.stdout))
        stderr_text, stderr_cut = self._decode(bytes(capture.stderr))
        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout_text,
            stderr=stderr_text,
            duration_seconds=time.monotonic() - started,
            timed_out=timed_out,
            truncated=capture.truncated or stdout_cut or stderr_cut,
        )

    def _drain(self, pipe, capture: _StreamCapture, key: str) -> None:
        if pipe is None:
            return
        limit = self.limits.max_output_bytes
        buf: bytearray = getattr(capture, key)
        try:
            while True:
                chunk = pipe.read(8192)
                if not chunk:
                    break
                with capture.lock:
                    room = limit - len(buf)
                    if room > 0:
                        buf.extend(chunk[:room])
                    if len(chunk) > max(room, 0):
                        capture.truncated = True
                        break
        except OSError:
            pass
        finally:
            try:
                pipe.close()
            except OSError:
                pass

    def _decode(self, data: bytes) -> tuple[str, bool]:
        truncated = False
        if len(data) > self.limits.max_output_bytes:
            data = data[: self.limits.max_output_bytes]
            truncated = True
        return data.decode("utf-8", errors="replace"), truncated

    def _kill_group(self, pid: int) -> None:
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    def _place_in_cgroup(self, pid: int) -> None:
        """Best-effort cgroup v2 memory, pid, and cpu caps. Skip when the kernel refuses."""
        if sys.platform != "linux":
            return
        parent = _current_cgroup_dir()
        if parent is None:
            return
        cgroup = parent / f"pari-{os.getpid()}-{pid}"
        try:
            cgroup.mkdir(exist_ok=True)
            memory_bytes = self.limits.memory_limit_mb * 1024 * 1024
            (cgroup / "memory.max").write_text(str(memory_bytes))
            (cgroup / "pids.max").write_text("256")
            (cgroup / "cpu.weight").write_text("100")
            (cgroup / "cgroup.procs").write_text(str(pid))
        except OSError:
            try:
                cgroup.rmdir()
            except OSError:
                pass
            return
        self._cgroups.append(cgroup)

    def _cleanup_processes(self) -> None:
        for pid in list(self._active_pgids):
            self._kill_group(pid)
        self._active_pgids.clear()
        for cgroup in self._cgroups:
            try:
                cgroup.rmdir()
            except OSError:
                pass
        self._cgroups.clear()


def _current_cgroup_dir() -> Optional[Path]:
    try:
        text = Path("/proc/self/cgroup").read_text()
    except OSError:
        return None
    for line in text.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[0] == "0":
            path = Path("/sys/fs/cgroup") / parts[2].lstrip("/")
            if path.is_dir():
                return path
    return None
