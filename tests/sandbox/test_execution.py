"""Command execution, timeout, and cgroup reporting."""

from pathlib import Path

from pari.sandbox.base import SandboxLimits
from pari.sandbox.dispatcher import get_sandbox_runner


def test_command_execution(tmp_path: Path):
    runner = get_sandbox_runner(tmp_path)
    res = runner.run_command("echo 'hello sandbox'")
    assert res.exit_code == 0
    assert "hello sandbox" in res.stdout
    assert not res.timed_out
    assert isinstance(res.cgroup_applied, bool)


def test_timeout_enforcement(tmp_path: Path):
    limits = SandboxLimits(timeout_seconds=0.5)
    runner = get_sandbox_runner(tmp_path, limits=limits)
    res = runner.run_command("sleep 5")
    assert res.timed_out is True
