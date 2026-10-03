"""PARI Layer 0: Base Sandbox Interface.

Defines the contract for all platform sandbox implementations (Bubblewrap, Seatbelt, E2B, ProcessGroup).
All commands executed by PARI must run through an implementation of SandboxRunner.

Guarantees:
    1. Working directory isolation: Writes restricted to authorized workspace tree.
    2. Die-with-parent lifecycle: Child processes killed when agent process terminates.
    3. Resource bounding: Execution constrained by timeout, max output bytes, and memory.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class SandboxLimits:
    """Resource constraints for sandboxed command execution."""
    timeout_seconds: float = 30.0
    max_output_bytes: int = 50 * 1024  # 50KB default spool cap
    memory_limit_mb: int = 2048        # 2GB cgroup ceiling
    allow_network: bool = True         # Disabling network isolates network calls


@dataclass
class SandboxResult:
    """Structured result from sandboxed command execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    truncated: bool = False
    spool_path: Optional[Path] = None


class SandboxRunner(ABC):
    """Abstract base class for all PARI kernel and cloud sandboxes."""

    def __init__(self, workspace: Path, limits: Optional[SandboxLimits] = None):
        self.workspace = workspace.resolve()
        self.limits = limits or SandboxLimits()

    @abstractmethod
    def run_command(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        """Execute a shell command inside the sandbox.
        
        Args:
            command: Shell command string to execute.
            env: Optional environment variables to inject.
            timeout: Optional override for maximum execution time in seconds.
            
        Returns:
            SandboxResult containing exit code, stdout, stderr, and resource metrics.
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Terminate any lingering child processes, virtual mounts, or microVM instances."""
        pass
