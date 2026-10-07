"""PARI Layer 0: macOS Apple Seatbelt Sandbox Runner.

Architectural Purpose:
    Uses macOS sandbox-exec with an explicit TinyScheme profile.
    Confines filesystem write operations strictly to the workspace directory.
    Note: Expands explicit user home path since Seatbelt TinyScheme does not expand tilde (~).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Dict, Optional

from pari.sandbox.base import SandboxLimits, SandboxResult, SandboxRunner, network_allowed, scrub_env

_SANDBOX_EXEC = "/usr/bin/sandbox-exec"


class MacOSSeatbeltSandboxRunner(SandboxRunner):
    """Runs commands in an Apple Seatbelt sandbox via sandbox-exec."""

    def __init__(self, workspace: Path, limits: Optional[SandboxLimits] = None):
        super().__init__(workspace, limits)
        if not Path(_SANDBOX_EXEC).is_file() and shutil.which("sandbox-exec") is None:
            raise FileNotFoundError("sandbox-exec is not available on this Mac")
        self._sandbox_exec = _SANDBOX_EXEC if Path(_SANDBOX_EXEC).is_file() else shutil.which("sandbox-exec")
        self._profile_path: Optional[Path] = None

    def run_command(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        child_env = scrub_env(env, home="/private/tmp")
        profile = render_seatbelt_profile(
            self.workspace,
            Path.home().resolve(),
            allow_network=network_allowed(command, self.limits),
            read_only=self.limits.read_only,
        )
        handle = tempfile.NamedTemporaryFile(
            "w", prefix="pari-seatbelt-", suffix=".sb", delete=False
        )
        handle.write(profile)
        handle.close()
        profile_path = Path(handle.name)
        self._profile_path = profile_path
        shell = "/bin/sh" if Path("/bin/sh").exists() else "/bin/bash"
        try:
            return self._execute(
                [self._sandbox_exec, "-f", str(profile_path), shell, "-c", command],
                cwd=self.workspace,
                env=child_env,
                timeout=timeout if timeout is not None else self.limits.timeout_seconds,
            )
        finally:
            try:
                profile_path.unlink()
            except OSError:
                pass
            self._profile_path = None

    def cleanup(self) -> None:
        self._cleanup_processes()
        if self._profile_path is not None:
            try:
                self._profile_path.unlink()
            except OSError:
                pass
            self._profile_path = None


def render_seatbelt_profile(
    workspace: Path,
    home: Path,
    *,
    allow_network: bool,
    read_only: bool,
) -> str:
    """Build the Layer 0 Seatbelt profile with absolute home and workspace paths."""
    workspace_s = _scheme_string(str(workspace))
    git_s = _scheme_string(str(workspace / ".git"))
    write_rule = "" if read_only else f"(allow file-read* file-write* (subpath {workspace_s}))"
    read_rule = f"(allow file-read* (subpath {workspace_s}))" if read_only else ""
    network_rule = ""
    if allow_network:
        network_rule = """
(allow network-outbound
    (remote tcp "*:443")
    (remote tcp "*:80")
    (remote tcp "*:53"))
"""
    return f"""(version 1)
(deny default)
(allow process-exec)
(allow process-fork)
(allow signal (target self))
(allow sysctl-read)
(allow file-ioctl (literal "/dev/null") (literal "/dev/zero") (literal "/dev/dtracehelper") (literal "/dev/random") (literal "/dev/urandom"))
(allow file-read*
    (subpath "/usr")
    (subpath "/bin")
    (subpath "/sbin")
    (subpath "/System")
    (subpath "/Library")
    (subpath "/Applications")
    (subpath "/Library/Developer/CommandLineTools")
    (subpath "/opt/homebrew")
    (subpath "/dev")
    (subpath "/private/etc"))
{read_rule}
{write_rule}
(deny file-write* (subpath {git_s}))
(allow file-read* file-write*
    (subpath "/private/tmp")
    (subpath "/private/var/folders"))
(deny file*
    (subpath {_scheme_string(str(home / ".ssh"))})
    (subpath {_scheme_string(str(home / ".aws"))})
    (subpath {_scheme_string(str(home / ".gnupg"))})
    (subpath {_scheme_string(str(home / ".config"))}))
{network_rule}
(deny network-inbound)
"""


def _scheme_string(path: str) -> str:
    escaped = path.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
