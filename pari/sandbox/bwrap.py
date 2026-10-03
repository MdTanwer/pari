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

from pathlib import Path
from typing import Dict, List, Optional
from pari.sandbox.base import SandboxLimits, SandboxResult, SandboxRunner


class BwrapSandboxRunner(SandboxRunner):
    """Runs commands in an unprivileged Linux Bubblewrap (bwrap) sandbox."""

    def __init__(self, workspace: Path, limits: Optional[SandboxLimits] = None):
        super().__init__(workspace, limits)
        # TODO: Verify 'bwrap' executable exists in PATH

    def run_command(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        # TODO: Assemble bwrap CLI arguments:
        # --die-with-parent, --ro-bind / /, --bind workspace workspace,
        # mask sensitive directories (~/.ssh, ~/.gnupg), and spawn child process
        raise NotImplementedError("Bwrap sandbox runner placeholder.")

    def cleanup(self) -> None:
        # TODO: Clean up any ephemeral mounts
        pass
