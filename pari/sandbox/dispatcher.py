"""PARI Layer 0: Sandbox Selection Dispatcher.

Architectural Purpose:
    Intelligently inspects the host platform and environment configuration
    to select the most secure available sandbox engine:
    1. Cloud mode -> E2B Firecracker MicroVM
    2. Linux / WSL2 with bwrap -> Bubblewrap runner
    3. macOS -> Apple Seatbelt runner
    4. Fallback / Native Windows -> Supervised Process Group runner
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from pari.sandbox.base import SandboxLimits, SandboxRunner
from pari.sandbox.bwrap import BwrapSandboxRunner
from pari.sandbox.e2b import E2BCloudSandboxRunner
from pari.sandbox.process import SupervisedProcessRunner
from pari.sandbox.seatbelt import MacOSSeatbeltSandboxRunner


def get_sandbox_runner(
    workspace: Path,
    limits: Optional[SandboxLimits] = None,
    force_mode: Optional[str] = None,
) -> SandboxRunner:
    """Select and instantiate the appropriate sandbox runner for the current platform.

    Mode comes from force_mode, then PARI_SANDBOX, then PARI_SANDBOX_MODE.
    auto picks bwrap on Linux when it is installed, Seatbelt on macOS, and the
    supervised process runner otherwise.
    """
    mode = (
        force_mode
        or os.environ.get("PARI_SANDBOX")
        or os.environ.get("PARI_SANDBOX_MODE")
        or "auto"
    ).lower()

    if mode == "cloud":
        return E2BCloudSandboxRunner(workspace, limits=limits)
    if mode == "bwrap":
        return BwrapSandboxRunner(workspace, limits=limits)
    if mode == "seatbelt":
        return MacOSSeatbeltSandboxRunner(workspace, limits=limits)
    if mode in {"none", "process", "supervised"}:
        return SupervisedProcessRunner(workspace, limits=limits)
    if mode != "auto":
        raise ValueError(f"Unknown sandbox mode: {mode}")

    if sys.platform == "linux" and shutil.which("bwrap"):
        return BwrapSandboxRunner(workspace, limits=limits)
    if sys.platform == "darwin" and shutil.which("sandbox-exec"):
        return MacOSSeatbeltSandboxRunner(workspace, limits=limits)
    return SupervisedProcessRunner(workspace, limits=limits)
