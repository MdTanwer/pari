"""PARI Layer 0: Sandbox Selection Dispatcher.

v1 selects Bubblewrap. Seatbelt, E2B, and the supervised process runner
raise until those backends are implemented.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pari.sandbox.base import SandboxLimits, SandboxRunner
from pari.sandbox.bwrap import BwrapSandboxRunner


_COMING_SOON = {
    "cloud": "E2B cloud sandbox is coming soon.",
    "seatbelt": "macOS Seatbelt sandbox is coming soon.",
    "none": "Unsandboxed process mode is coming soon.",
    "process": "Supervised process mode is coming soon.",
    "supervised": "Supervised process mode is coming soon.",
}


def get_sandbox_runner(
    workspace: Path,
    limits: SandboxLimits | None = None,
    force_mode: str | None = None,
) -> SandboxRunner:
    """Select the sandbox runner.

    Mode comes from force_mode, then PARI_SANDBOX, then PARI_SANDBOX_MODE.
    auto and bwrap use Bubblewrap. On a non-Linux host, auto raises instead
    of running the command on the host.
    """
    mode = (
        force_mode
        or os.environ.get("PARI_SANDBOX")
        or os.environ.get("PARI_SANDBOX_MODE")
        or "auto"
    ).lower()

    if mode in {"auto", "bwrap"}:
        if mode == "auto" and sys.platform != "linux":
            raise NotImplementedError(
                f"Sandbox support for {sys.platform} is coming soon."
            )
        return BwrapSandboxRunner(workspace, limits=limits)
    if mode in _COMING_SOON:
        raise NotImplementedError(_COMING_SOON[mode])
    raise ValueError(f"Unknown sandbox mode: {mode}")
