"""Unit tests for Layer 0 Sandboxing & Process Execution."""

import shlex
from pathlib import Path

from pari.sandbox.base import SandboxLimits
from pari.sandbox.dispatcher import get_sandbox_runner


def test_sandbox_dispatcher_and_command_execution(tmp_path: Path):
    runner = get_sandbox_runner(tmp_path)
    res = runner.run_command("echo 'hello sandbox'")
    assert res.exit_code == 0
    assert "hello sandbox" in res.stdout
    assert not res.timed_out


def test_sandbox_timeout_enforcement(tmp_path: Path):
    limits = SandboxLimits(timeout_seconds=0.5)
    runner = get_sandbox_runner(tmp_path, limits=limits)
    res = runner.run_command("sleep 5")
    assert res.timed_out is True


def test_sandbox_workspace_write_and_outside_path_hidden(tmp_path: Path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret")
    runner = get_sandbox_runner(workspace)
    quoted = shlex.quote(str(secret))
    res = runner.run_command(
        f"touch probe.txt && test ! -f {quoted} && echo hidden"
    )
    assert res.exit_code == 0, res.stderr
    assert "hidden" in res.stdout
    assert (workspace / "probe.txt").is_file()


def test_sandbox_system_path_is_read_only(tmp_path: Path):
    probe = Path("/usr/pari-sandbox-probe")
    if probe.exists():
        probe.unlink()
    runner = get_sandbox_runner(tmp_path)
    res = runner.run_command("touch /usr/pari-sandbox-probe")
    assert res.exit_code != 0
    assert not probe.exists()
