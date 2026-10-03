"""PARI Layer 0: Base Sandbox Interface.

Defines the contract for all platform sandbox implementations (Bubblewrap, Seatbelt, E2B, ProcessGroup).
All commands executed by PARI must run through an implementation of SandboxRunner.

Guarantees:
    1. Working directory isolation: Writes restricted to authorized workspace tree.
    2. Die-with-parent lifecycle: Child processes killed when agent process terminates.
    3. Resource bounding: Execution constrained by timeout, max output bytes, and memory.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


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


class SandboxRunner(ABC):
    """Abstract base class for all PARI kernel and cloud sandboxes."""

    def __init__(self, workspace: Path, limits: Optional[SandboxLimits] = None):
        # TODO: Initialize workspace path and enforce resource limits
        pass

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
