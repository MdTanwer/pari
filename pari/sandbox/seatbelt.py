"""PARI Layer 0: macOS Apple Seatbelt Sandbox Runner.

TODO: run commands with sandbox-exec and a TinyScheme profile.
Home paths must be absolute. Seatbelt does not expand '~'.

``allow_git_write`` and ``allow_secrets`` are honored by Bubblewrap. This
runner does not execute commands yet, so it cannot apply them. The profile
must mount the workspace ``.git`` read-write only when ``allow_git_write``
is set, and must leave ``.ssh``, ``.aws``, ``.gnupg``, and credential files
visible only when ``allow_secrets`` is set. ``granted_env`` must be added to
the child environment after scrubbing, as Bubblewrap does.
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
        _ = (command, env, timeout, on_output)
        raise NotImplementedError("macOS Seatbelt sandbox is coming soon.")

    def cleanup(self) -> None:
        raise NotImplementedError("macOS Seatbelt sandbox is coming soon.")
