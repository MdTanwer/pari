"""PARI Layer 0: Multi-Platform Kernel Sandboxing Engine.

Architectural Purpose:
    Closes Claude Code F2, Pi F1, Aider F1, and OpenCode F1.
    Prevents hallucinated or prompt-injected destructive commands (e.g., rm -rf /)
    from executing with host-user privileges.

Subsystems:
    - dispatcher: Automatically selects the most secure sandbox backend based on OS
    - bwrap: Linux & Windows WSL2 bubblewrap container isolation (<5ms startup)
    - seatbelt: macOS Apple Seatbelt (sandbox-exec + Scheme profile)
    - e2b: Cloud microVM execution using Firecracker KVM
    - process: Process-group supervision, die-with-parent lifecycle, and zombie reaping
"""

from pari.sandbox.base import SandboxLimits, SandboxResult, SandboxRunner
from pari.sandbox.bwrap import BwrapSandboxRunner
from pari.sandbox.dispatcher import get_sandbox_runner
from pari.sandbox.process import SupervisedProcessRunner


__all__ = [
    "BwrapSandboxRunner",
    "SandboxLimits",
    "SandboxResult",
    "SandboxRunner",
    "SupervisedProcessRunner",
    "get_sandbox_runner",
]
