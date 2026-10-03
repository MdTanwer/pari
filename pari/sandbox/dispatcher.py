"""PARI Layer 0: Sandbox Selection Dispatcher.

Architectural Purpose:
    Intelligently inspects the host platform and environment configuration
    to select the most secure available sandbox engine:
    1. Cloud mode -> E2B Firecracker MicroVM
    2. Linux / WSL2 with bwrap -> Bubblewrap runner
    3. macOS -> Apple Seatbelt runner
    4. Fallback / Native Windows -> Supervised Process Group runner
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from pari.sandbox.base import SandboxLimits, SandboxRunner
from pari.sandbox.process import SupervisedProcessRunner


def get_sandbox_runner(
    workspace: Path,
    limits: Optional[SandboxLimits] = None,
    force_mode: Optional[str] = None,
) -> SandboxRunner:
    """Select and instantiate the appropriate sandbox runner for the current platform.
    
    Args:
        workspace: Path to working repository root.
        limits: Optional resource limits.
        force_mode: Explicit engine override ('bwrap', 'seatbelt', 'e2b', 'process').
    """
    mode = force_mode or os.environ.get("PARI_SANDBOX_MODE")

    if mode == "cloud" or mode == "e2b":
        from pari.sandbox.e2b import E2BCloudSandboxRunner
        return E2BCloudSandboxRunner(workspace, limits)

    if (mode == "bwrap" or (mode is None and sys.platform.startswith("linux"))) and shutil.which("bwrap"):
        from pari.sandbox.bwrap import BwrapSandboxRunner
        return BwrapSandboxRunner(workspace, limits)

    if (mode == "seatbelt" or (mode is None and sys.platform == "darwin")) and shutil.which("sandbox-exec"):
        from pari.sandbox.seatbelt import MacOSSeatbeltSandboxRunner
        return MacOSSeatbeltSandboxRunner(workspace, limits)

    # Supervised process group fallback for Linux without bwrap, or native Windows
    return SupervisedProcessRunner(workspace, limits)
