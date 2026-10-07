"""PARI Layer 0: Base Sandbox Interface.

Defines the contract for Bubblewrap, Seatbelt, E2B, and the process-group runner.
All commands executed by PARI must run through a SandboxRunner.

Guarantees:
    1. Working directory isolation: writes stay inside the workspace.
    2. Die-with-parent lifecycle: children die when the agent process dies.
    3. Resource bounding: timeout, output bytes, and memory are capped.
"""

from __future__ import annotations

import ctypes
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


_SECRET_ENV_MARKERS = (
    "KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "CREDENTIAL",
    "COOKIE",
)
_SECRET_ENV_NAMES = {"SSH_AUTH_SOCK", "SSH_AGENT_PID"}
SANDBOX_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
# Binding one of these as the workspace would undo the read-only system mounts.
_FORBIDDEN_WORKSPACES = frozenset(
    {
        "/",
        "/usr",
        "/bin",
        "/lib",
        "/lib64",
        "/etc",
        "/sbin",
        "/proc",
        "/dev",
        "/sys",
        "/root",
        "/home",
    }
)


def scrub_env(
    extra: dict[str, str] | None = None,
    *,
    home: str,
    path: str = SANDBOX_PATH,
) -> dict[str, str]:
    """Build a minimal environment that does not forward host credentials."""
    env = {
        "PATH": path,
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
        allow_network: Share the host network for every command.
        allow_package_network: Network for one package-install command only.
        read_only: Mount the workspace read-only.
    """

    timeout_seconds: float = 30.0
    max_output_bytes: int = 50 * 1024
    memory_limit_mb: int = 2048
    allow_network: bool = False
    allow_package_network: bool = True
    read_only: bool = False


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
        cgroup_applied: True when memory.max, pids.max, and cpu.weight were set.
    """

    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    truncated: bool = False
    cgroup_applied: bool = False


_PACKAGE_BINS = frozenset(
    {"pip", "pip3", "npm", "pnpm", "yarn", "cargo", "poetry", "uv"}
)
_PACKAGE_SUBCOMMANDS = frozenset({"install", "add", "update", "fetch", "sync"})
_SHELL_COMPOSERS = (";", "&&", "||", "|", "`", "$(", "\n", ">", "<")


def network_allowed(command: str, limits: SandboxLimits) -> bool:
    """Share the network only when asked, or for one package-install command.

    ``pip install x; curl`` does not receive the network.
    """
    if limits.allow_network:
        return True
    if not limits.allow_package_network:
        return False
    if any(marker in command for marker in _SHELL_COMPOSERS):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if len(parts) < 2:
        return False
    binary = Path(parts[0]).name
    return binary in _PACKAGE_BINS and parts[1] in _PACKAGE_SUBCOMMANDS


@dataclass
class _StreamCapture:
    stdout: bytearray = field(default_factory=bytearray)
    stderr: bytearray = field(default_factory=bytearray)
    truncated: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


class SandboxRunner(ABC):
    """Abstract base class for all PARI kernel and cloud sandboxes."""

    def __init__(self, workspace: Path, limits: SandboxLimits | None = None):
        self.workspace = Path(workspace).resolve()
        if not self.workspace.is_dir():
            raise NotADirectoryError(f"Workspace is not a directory: {self.workspace}")
        if str(self.workspace) in _FORBIDDEN_WORKSPACES:
            raise ValueError(
                f"Refusing to sandbox a system directory: {self.workspace}"
            )
        self.limits = limits or SandboxLimits()
        self._active_pgids: set[int] = set()
        self._cgroups: list[Path] = []

    @abstractmethod
    def run_command(
        self,
        command: str,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> SandboxResult:
        """Execute a shell command inside the sandbox."""
        raise NotImplementedError

    @abstractmethod
    def cleanup(self) -> None:
        """Stop leftover child processes, mounts, or microVMs."""
        raise NotImplementedError

    def _child_setup(self) -> None:
        """Run in the forked child: new process group, die with parent, memory cap."""
        os.setsid()
        if sys.platform == "linux":
            libc = ctypes.CDLL(None, use_errno=True)
            libc.prctl(1, signal.SIGKILL)  # PR_SET_PDEATHSIG = 1
            if os.getppid() == 1:
                os._exit(1)

    def _execute(
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: float,
        preexec: Callable[[], None] | None = None,
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
        cgroup_applied = self._place_in_cgroup(proc.pid)
        capture = _StreamCapture()
        threads = [
            threading.Thread(
                target=self._drain, args=(proc.stdout, capture, "stdout"), daemon=True
            ),
            threading.Thread(
                target=self._drain, args=(proc.stderr, capture, "stderr"), daemon=True
            ),
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
            cgroup_applied=cgroup_applied,
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

    def _place_in_cgroup(self, pid: int) -> bool:
        """Apply memory, pid, and cpu caps. False if the kernel refuses."""
        if sys.platform != "linux":
            return False
        parent = _current_cgroup_dir()
        if parent is None:
            return False
        cgroup = parent / f"pari-{os.getpid()}-{pid}"
        try:
            cgroup.mkdir(exist_ok=True)
            memory_bytes = self.limits.memory_limit_mb * 1024 * 1024
            (cgroup / "memory.max").write_text(str(memory_bytes))
            (cgroup / "pids.max").write_text("256")
            (cgroup / "cpu.weight").write_text("100")
            (cgroup / "cgroup.procs").write_text(str(pid))
            members = (cgroup / "cgroup.procs").read_text().split()
            if str(pid) not in members:
                raise OSError("process was not placed in the cgroup")
        except OSError:
            try:
                cgroup.rmdir()
            except OSError:
                pass
            return False
        self._cgroups.append(cgroup)
        return True

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


def _current_cgroup_dir() -> Path | None:
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
