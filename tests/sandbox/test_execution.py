"""Command execution, timeout, and cgroup reporting."""

import time
from pathlib import Path

import pytest

from pari.sandbox.base import SandboxLimits
from pari.sandbox.dispatcher import get_sandbox_runner


def test_granted_env_reaches_the_command_and_host_tokens_do_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("GH_TOKEN", "host-token")
    plain = get_sandbox_runner(tmp_path).run_command('echo "[$GH_TOKEN]"')
    assert plain.exit_code == 0, plain.stderr
    assert "[]" in plain.stdout
    limits = SandboxLimits(granted_env={"GH_TOKEN": "approved"})
    granted = get_sandbox_runner(tmp_path, limits=limits).run_command(
        'echo "[$GH_TOKEN]"'
    )
    assert granted.exit_code == 0, granted.stderr
    assert "[approved]" in granted.stdout


def test_output_arrives_before_the_command_exits(tmp_path: Path):
    runner = get_sandbox_runner(tmp_path)
    seen: list[tuple[float, str]] = []

    def on_output(_stream: str, text: str) -> None:
        seen.append((time.monotonic(), text))

    result = runner.run_command(
        "echo one && sleep 0.5 && echo two", on_output=on_output
    )
    assert result.exit_code == 0
    one_at = next(stamp for stamp, text in seen if "one" in text)
    two_at = next(stamp for stamp, text in seen if "two" in text)
    assert two_at - one_at >= 0.2
    assert "two" in result.stdout


def test_command_runs_when_the_host_has_no_pty(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("pari.sandbox.base.pty", None)
    runner = get_sandbox_runner(tmp_path)
    seen: list[str] = []

    def on_output(_stream: str, text: str) -> None:
        seen.append(text)

    result = runner.run_command("echo hello", on_output=on_output)
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert any("hello" in text for text in seen)


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


def test_daemon_idle_stops_a_command_that_does_not_exit(tmp_path: Path):
    limits = SandboxLimits(timeout_seconds=30, daemon_idle_seconds=1)
    runner = get_sandbox_runner(tmp_path, limits=limits)
    # sleep inherits the ignored SIGINT, so only the later SIGKILL can stop it.
    res = runner.run_command("trap '' INT; sleep 30")
    assert res.daemon is True
    assert res.timed_out is True
    assert res.duration_seconds < 5
    assert _pids_with_cmdline("sleep 30") == []


def test_timeout_enforcement(tmp_path: Path):
    limits = SandboxLimits(timeout_seconds=0.5)
    runner = get_sandbox_runner(tmp_path, limits=limits)
    res = runner.run_command("sleep 5")
    assert res.timed_out is True


def _pids_with_cmdline(expected: str) -> list[int]:
    found: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ")
        except OSError:
            continue
        if command.decode(errors="replace").strip() == expected:
            found.append(int(entry.name))
    return found
