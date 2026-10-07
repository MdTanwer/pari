"""PARI Layer 0: Linux / WSL2 Bubblewrap Sandbox Runner.

Architectural Purpose:
    Harvested from Codex codex-bwrap.
    Provides sub-5ms unprivileged user namespace isolation (zero root required).
    Mounts system paths read-only, the workspace read-write, and leaves
    ~/.ssh, ~/.aws, ~/.gnupg, and ~/.bashrc unmounted.
    Drops the network namespace when network isolation is requested.

Kernel Namespaces:
    - CLONE_NEWUSER, CLONE_NEWNS, CLONE_NEWPID, CLONE_NEWIPC, CLONE_NEWUTS.
    - Die-with-parent via bwrap --die-with-parent flag.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from pari.sandbox.base import SandboxLimits, SandboxResult, SandboxRunner, scrub_env


class BwrapSandboxRunner(SandboxRunner):
    """Runs commands in an unprivileged Linux Bubblewrap (bwrap) sandbox."""

    def __init__(self, workspace: Path, limits: Optional[SandboxLimits] = None):
        super().__init__(workspace, limits)
        bwrap = shutil.which("bwrap")
        if not bwrap:
            raise FileNotFoundError(
                "bubblewrap is not installed. Install it with: sudo apt install bubblewrap"
            )
        self._bwrap = bwrap

    def run_command(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        child_env = scrub_env(env, home="/tmp")
        argv = self._argv(command, child_env)
        return self._execute(
            argv,
            cwd=Path("/"),
            env=child_env,
            timeout=timeout if timeout is not None else self.limits.timeout_seconds,
        )

    def cleanup(self) -> None:
        self._cleanup_processes()

    def _argv(self, command: str, env: Dict[str, str]) -> List[str]:
        workspace = str(self.workspace)
        argv = [
            self._bwrap,
            "--die-with-parent",
            "--unshare-user",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--hostname",
            "pari-sandbox",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--chdir",
            workspace,
        ]
        if not self.limits.allow_network:
            argv.append("--unshare-net")
        _append_system_mounts(argv)
        argv.extend(["--bind", workspace, workspace])
        argv.append("--clearenv")
        for key, value in env.items():
            argv.extend(["--setenv", key, value])
        shell = "/bin/sh" if Path("/bin/sh").exists() else "/usr/bin/sh"
        argv.extend([shell, "-c", command])
        return argv


def _append_system_mounts(argv: List[str]) -> None:
    """Read-only system paths. Symlinks (merged /usr) stay symlinks so /usr is the real mount."""
    usr = Path("/usr")
    if usr.is_dir() and not usr.is_symlink():
        argv.extend(["--ro-bind", "/usr", "/usr"])
    for path in ("/bin", "/lib", "/lib64", "/sbin"):
        host_path = Path(path)
        if host_path.is_symlink():
            argv.extend(["--symlink", os.readlink(host_path), path])
        elif host_path.is_dir():
            argv.extend(["--ro-bind", path, path])
    if Path("/etc").is_dir() and not Path("/etc").is_symlink():
        argv.extend(["--ro-bind", "/etc", "/etc"])
