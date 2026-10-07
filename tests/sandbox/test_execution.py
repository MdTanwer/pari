"""Command execution, timeout, and cgroup reporting."""

from pathlib import Path

import pytest

from pari.sandbox.base import SandboxLimits
from pari.sandbox.dispatcher import get_sandbox_runner


def test_command_execution(tmp_path: Path):
    runner = get_sandbox_runner(tmp_path)
    res = runner.run_command("echo 'hello sandbox'")
    assert res.exit_code == 0
    assert "hello sandbox" in res.stdout
    assert not res.timed_out
    assert isinstance(res.cgroup_applied, bool)


@pytest.mark.parametrize(
    "mode",
    ["cloud", "seatbelt", "none", "process", "supervised"],
)
def test_other_modes_are_coming_soon(tmp_path: Path, mode: str):
    with pytest.raises(NotImplementedError, match="coming soon"):
        get_sandbox_runner(tmp_path, force_mode=mode)


def test_unknown_mode_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="Unknown sandbox mode"):
        get_sandbox_runner(tmp_path, force_mode="docker")


def test_timeout_enforcement(tmp_path: Path):
    limits = SandboxLimits(timeout_seconds=0.5)
    runner = get_sandbox_runner(tmp_path, limits=limits)
    res = runner.run_command("sleep 5")
    assert res.timed_out is True
