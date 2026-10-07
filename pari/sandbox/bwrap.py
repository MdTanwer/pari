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

from pari.sandbox.base import (
    SandboxLimits,
    SandboxResult,
    SandboxRunner,
    network_allowed,
    scrub_env,
)


class BwrapSandboxRunner(SandboxRunner):
    """Runs commands in an unprivileged Linux Bubblewrap (bwrap) sandbox."""

    def __init__(self, workspace: Path, limits: SandboxLimits | None = None):
        super().__init__(workspace, limits)
        self._bwrap = find_bwrap(self.workspace)

    def run_command(
        self,
        command: str,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
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

    def _argv(self, command: str, env: dict[str, str]) -> list[str]:
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
        if not network_allowed(command, self.limits):
            argv.append("--unshare-net")
        _append_system_mounts(argv)
        bind = "--ro-bind" if self.limits.read_only else "--bind"
        argv.extend([bind, workspace, workspace])
        _append_secret_masks(argv, self.workspace)
        argv.append("--clearenv")
        for key, value in env.items():
            argv.extend(["--setenv", key, value])
        shell = "/bin/sh" if Path("/bin/sh").exists() else "/usr/bin/sh"
        argv.extend([shell, "-c", command])
        return argv


# Credential directories from the Layer 0 secret blackout. .config is only
# masked when the workspace is the user home, because project trees use .config.
_SECRET_DIRS = (".ssh", ".aws", ".gnupg")
_HOME_ONLY_SECRET_DIRS = (".config",)
_SECRET_FILES = (".bashrc", ".profile", ".netrc", ".git-credentials")
_TRUSTED_BWRAP = ("/usr/bin/bwrap", "/usr/local/bin/bwrap", "/bin/bwrap")


def find_bwrap(workspace: Path) -> str:
    """Locate bubblewrap outside the workspace.

    A repository must not be able to supply the sandbox binary via PATH or cwd.
    """
    workspace = workspace.resolve()
    for candidate in _TRUSTED_BWRAP:
        path = Path(candidate)
        if not path.is_file() or not os.access(path, os.X_OK):
            continue
        resolved = path.resolve()
        if resolved == workspace or _is_inside(resolved, workspace):
            continue
        return str(path)
    found = shutil.which("bwrap")
    if found:
        resolved = Path(found).resolve()
        if resolved != workspace and not _is_inside(resolved, workspace):
            return str(resolved)
    raise FileNotFoundError(
        "bubblewrap is not installed. Install it with: sudo apt install bubblewrap"
    )


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _append_secret_masks(argv: list[str], workspace: Path) -> None:
    """Hide credential files that live inside the writable workspace mount."""
    names = list(_SECRET_DIRS)
    if workspace == Path.home().resolve():
        names.extend(_HOME_ONLY_SECRET_DIRS)
    for name in names:
        host_path = workspace / name
        if host_path.is_dir():
            argv.extend(["--tmpfs", str(host_path)])
    for name in _SECRET_FILES:
        host_path = workspace / name
        if host_path.is_file():
            argv.extend(["--ro-bind", "/dev/null", str(host_path)])
    git_dir = workspace / ".git"
    if git_dir.exists():
        argv.extend(["--ro-bind", str(git_dir), str(git_dir)])


def _append_system_mounts(argv: list[str]) -> None:
    """Mount system paths read-only. Merged-/usr symlinks stay symlinks."""
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
