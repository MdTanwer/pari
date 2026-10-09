"""PARI Layer 0: Cloud E2B Firecracker Sandbox Runner.

Architectural Purpose:
    Satisfies cloud microVM sandboxing using E2B Firecracker hardware KVM microVMs.
    Bypasses weeks of custom hypervisor / vsock plumbing while guaranteeing full
    kernel-level hardware virtualization for remote evaluation and cloud runs.
"""

from pathlib import Path

from pari.sandbox.base import SandboxLimits, SandboxResult, SandboxRunner


class E2BCloudSandboxRunner(SandboxRunner):
    """Executes commands inside an ephemeral E2B Firecracker Cloud microVM."""

    def __init__(
        self,
        workspace: Path,
        limits: SandboxLimits | None = None,
        api_key: str | None = None,
    ):
        super().__init__(workspace, limits)
        self._api_key = api_key

    def run_command(
        self,
        command: str,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> SandboxResult:
        # TODO: Execute command remotely inside Firecracker microVM
        raise NotImplementedError("E2B cloud sandbox is coming soon.")

    def cleanup(self) -> None:
        # TODO: Close remote microVM instance
        pass
