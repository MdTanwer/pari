"""PARI Layer 0: macOS Apple Seatbelt Sandbox Runner.

Architectural Purpose:
    Uses macOS sandbox-exec with an explicit TinyScheme profile.
    Confines filesystem write operations strictly to the workspace directory.
    Note: Expands explicit user home path since Seatbelt TinyScheme does not expand tilde (~).
"""

from pathlib import Path
from typing import Dict, Optional
from pari.sandbox.base import SandboxLimits, SandboxResult, SandboxRunner


class MacOSSeatbeltSandboxRunner(SandboxRunner):
    """Runs commands in an Apple Seatbelt sandbox via sandbox-exec."""

    def __init__(self, workspace: Path, limits: Optional[SandboxLimits] = None):
        super().__init__(workspace, limits)
        # TODO: Verify 'sandbox-exec' exists in PATH

    def run_command(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        # TODO: Generate TinyScheme profile restricting writes to workspace and /tmp,
        # denying ~/.ssh, ~/.aws, ~/.gnupg access, and execute via sandbox-exec -f
        raise NotImplementedError("macOS Seatbelt sandbox runner placeholder.")

    def cleanup(self) -> None:
        pass
