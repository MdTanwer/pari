"""PARI Layer 0: macOS Apple Seatbelt Sandbox Runner.

TODO: run commands with sandbox-exec and a TinyScheme profile.
Home paths must be absolute. Seatbelt does not expand '~'.
"""

from collections.abc import Callable
from pathlib import Path

from pari.sandbox.base import SandboxLimits, SandboxResult, SandboxRunner


class MacOSSeatbeltSandboxRunner(SandboxRunner):
    """Runs commands in an Apple Seatbelt sandbox via sandbox-exec."""

    def __init__(self, workspace: Path, limits: SandboxLimits | None = None):
        super().__init__(workspace, limits)

    def run_command(
        self,
        command: str,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
        on_output: Callable[[str, str], None] | None = None,
    ) -> SandboxResult:
        # TODO: write the Seatbelt profile and exec sandbox-exec.
        _ = (command, env, timeout, on_output)
        raise NotImplementedError("macOS Seatbelt sandbox is coming soon.")

    def cleanup(self) -> None:
        # TODO: remove the temporary profile and stop leftover children.
        pass
