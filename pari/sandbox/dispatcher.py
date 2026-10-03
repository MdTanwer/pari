"""PARI Layer 0: Sandbox Selection Dispatcher.

Architectural Purpose:
    Intelligently inspects the host platform and environment configuration
    to select the most secure available sandbox engine:
    1. Cloud mode -> E2B Firecracker MicroVM
    2. Linux / WSL2 with bwrap -> Bubblewrap runner
    3. macOS -> Apple Seatbelt runner
    4. Fallback / Native Windows -> Supervised Process Group runner
"""

from pathlib import Path
from typing import Optional
from pari.sandbox.base import SandboxLimits, SandboxRunner


def get_sandbox_runner(
    workspace: Path,
    limits: Optional[SandboxLimits] = None,
    force_mode: Optional[str] = None,
) -> SandboxRunner:
    """Select and instantiate the appropriate sandbox runner for the current platform.
    
    TODO:
    - Check force_mode or PARI_SANDBOX_MODE env var.
    - If cloud -> E2BCloudSandboxRunner
    - If Linux and bwrap in PATH -> BwrapSandboxRunner
    - If macOS and sandbox-exec in PATH -> MacOSSeatbeltSandboxRunner
    - Otherwise -> SupervisedProcessRunner fallback
    """
    raise NotImplementedError("Sandbox selection dispatcher placeholder.")
