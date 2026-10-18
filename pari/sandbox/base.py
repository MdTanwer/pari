"""PARI Layer 0: Base Sandbox Interface.

Defines the contract for Bubblewrap, Seatbelt, E2B, and the process-group runner.
All commands executed by PARI must run through a SandboxRunner.

Guarantees:
    1. Working directory isolation: writes stay inside the workspace.
    2. Die-with-parent lifecycle: children die when the agent process dies.
    3. Resource bounding: timeout, output bytes, and memory are capped.
"""

from __future__ import annotations

import codecs
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


try:
    import pty
except ImportError:
    pty = None  # Windows has no pty module.


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
        allow_git_write: Leave .git writable for this command.
        allow_secrets: Leave secret directories and credential files visible.
        granted_env: Variables the user approved for this command, such as a
            GitHub token for one push. Set after scrubbing, so names that look
            like credentials are kept.
        daemon_idle_seconds: Stop waiting when a command is still running
            after this many seconds. None keeps the hard timeout only.
    """

    timeout_seconds: float = 30.0
    max_output_bytes: int = 50 * 1024
    memory_limit_mb: int = 2048
    allow_network: bool = False
    allow_package_network: bool = True
    read_only: bool = False
    allow_git_write: bool = False
    allow_secrets: bool = False
    granted_env: dict[str, str] = field(default_factory=dict)
    daemon_idle_seconds: float | None = None


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
        daemon: True when the idle window ended the wait before the hard timeout.
    """

    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    truncated: bool = False
    cgroup_applied: bool = False
    daemon: bool = False


_PACKAGE_BINS = frozenset(
    {"pip", "pip3", "npm", "pnpm", "yarn", "cargo", "poetry", "uv"}
)
_PACKAGE_SUBCOMMANDS = frozenset({"install", "add", "update", "fetch", "sync"})
# `&` backgrounds the install and runs the rest of the line with its network.
_SHELL_COMPOSERS = (";", "&&", "||", "|", "&", "`", "$(", "\n", ">", "<")
_SHELL_OPERATORS = frozenset(
    {
        "&",
        "&&",
        "|",
        "||",
        "|&",
        ";",
        ";;",
        "(",
        ")",
        "{",
        "}",
        "<",
        "<<",
        "<<<",
        ">",
        ">>",
        "<&",
        ">&",
        "<>",
        ">|",
        "`",
        "$(",
    }
)


def network_allowed(command: str, limits: SandboxLimits) -> bool:
    """Share the network only when asked, or for one package-install command.

    ``pip install x; curl`` and ``pip install x & curl`` do not receive the
    network. A URL argument such as ``--index-url http://…`` does not either,
    unless ``allow_network`` is set.
    """
    if limits.allow_network:
        return True
    if not limits.allow_package_network:
        return False
    # shlex glues ";" onto the previous word and drops newlines.
    if any(marker in command for marker in _SHELL_COMPOSERS):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return len(parts) >= 2 and _single_package_argv(parts)


def is_package_install(command: str) -> bool:
    """True for one package-install command, with no shell composers or URLs."""
    return network_allowed(command, SandboxLimits())


def _single_package_argv(parts: list[str]) -> bool:
    """True when every token is a package-install argument, not a shell or URL."""
    if any(part in _SHELL_OPERATORS for part in parts):
        return False
    if any(_points_at_url(part) for part in parts):
        return False
    binary = Path(parts[0]).name
    return binary in _PACKAGE_BINS and parts[1] in _PACKAGE_SUBCOMMANDS


def _points_at_url(token: str) -> bool:
    """True when a token names a host, including ``--index-url=http://…``."""
    return "://" in token.lower()


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
        on_output: Callable[[str, str], None] | None = None,
    ) -> SandboxResult:
        """Execute a shell command inside the sandbox.

        ``on_output(stream, text)`` is called as stdout and stderr arrive.
        ``stream`` is ``"stdout"`` or ``"stderr"``.
        """
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
        on_output: Callable[[str, str], None] | None = None,
    ) -> SandboxResult:
        """Run argv with a timeout, an output cap, and process-group teardown."""
        started = time.monotonic()
        # A tty flushes each line. A pipe holds the output until the process exits.
        # Layer 4 runs commands on a PTY. Fall back to pipes when the host has none.
        master, slave = (None, None)
        if on_output is not None and pty is not None:
            try:
                master, slave = pty.openpty()
            except OSError:
                master, slave = (None, None)
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=slave if slave is not None else subprocess.PIPE,
            stderr=slave if slave is not None else subprocess.PIPE,
            preexec_fn=preexec or self._child_setup,
            close_fds=True,
        )
        if slave is not None:
            os.close(slave)
        self._active_pgids.add(proc.pid)
        cgroup_applied = self._place_in_cgroup(proc.pid)
        capture = _StreamCapture()
        if master is not None:
            terminal = os.fdopen(master, "rb", buffering=0)
            threads = [
                threading.Thread(
                    target=self._drain,
                    args=(terminal, capture, "stdout", on_output),
                    daemon=True,
                )
            ]
        else:
            threads = [
                threading.Thread(
                    target=self._drain,
                    args=(proc.stdout, capture, "stdout", on_output),
                    daemon=True,
                ),
                threading.Thread(
                    target=self._drain,
                    args=(proc.stderr, capture, "stderr", on_output),
                    daemon=True,
                ),
            ]
        for thread in threads:
            thread.start()

        timed_out = False
        daemon = False
        deadline = started + timeout
        # Layer 4: a server that never exits must not freeze the turn.
        # SIGINT is the Ctrl+C a PTY would send this process group.
        # The hard timeout still kills the group if the command outlives it.
        idle_at = None
        if self.limits.daemon_idle_seconds is not None:
            idle_at = started + self.limits.daemon_idle_seconds
        while proc.poll() is None:
            now = time.monotonic()
            if capture.truncated or now >= deadline:
                timed_out = not capture.truncated and now >= deadline
                self._kill_group(proc.pid)
                break
            if idle_at is not None and now >= idle_at:
                daemon = True
                timed_out = True
                self._signal_group(proc.pid, signal.SIGINT)
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
            daemon=daemon,
        )

    def _drain(
        self,
        pipe,
        capture: _StreamCapture,
        key: str,
        on_output: Callable[[str, str], None] | None,
    ) -> None:
        if pipe is None:
            return
        limit = self.limits.max_output_bytes
        buf: bytearray = getattr(capture, key)
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            while True:
                chunk = pipe.read(8192)
                if not chunk:
                    break
                with capture.lock:
                    room = limit - len(buf)
                    accepted = chunk[:room] if room > 0 else b""
                    accepted = accepted.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                    if accepted:
                        buf.extend(accepted)
                    overflow = len(chunk) > max(room, 0)
                    if overflow:
                        capture.truncated = True
                self._emit(on_output, key, decoder, accepted)
                if overflow:
                    break
        except OSError:
            pass
        finally:
            self._emit(on_output, key, decoder, b"", final=True)
            try:
                pipe.close()
            except OSError:
                pass

    def _emit(
        self,
        on_output: Callable[[str, str], None] | None,
        stream: str,
        decoder: codecs.IncrementalDecoder,
        data: bytes,
        *,
        final: bool = False,
    ) -> None:
        if on_output is None:
            return
        text = decoder.decode(data, final)
        if text:
            on_output(stream, text)

    def _decode(self, data: bytes) -> tuple[str, bool]:
        truncated = False
        if len(data) > self.limits.max_output_bytes:
            data = data[: self.limits.max_output_bytes]
            truncated = True
        return data.decode("utf-8", errors="replace"), truncated

    def _signal_group(self, pid: int, sig: int) -> None:
        try:
            os.killpg(pid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    def _kill_group(self, pid: int) -> None:
        self._signal_group(pid, signal.SIGKILL)

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
