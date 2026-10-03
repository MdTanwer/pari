"""Unit tests for Layer 0 Sandboxing & Process Execution."""

from pathlib import Path
from pari.sandbox.dispatcher import get_sandbox_runner
from pari.sandbox.base import SandboxLimits


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
