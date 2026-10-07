"""Network stays off except for a single package install."""

from pathlib import Path

from pari.sandbox.base import SandboxLimits, network_allowed
from pari.sandbox.bwrap import BwrapSandboxRunner


def _interfaces(stdout: str) -> list[str]:
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def test_network_unshared_by_default(tmp_path: Path):
    runner = BwrapSandboxRunner(tmp_path)
    res = runner.run_command("awk -F: '/^ *[a-z0-9]+:/ {print $1}' /proc/net/dev")
    assert res.exit_code == 0, res.stderr
    assert _interfaces(res.stdout) == ["lo"]


def test_composed_package_command_stays_offline(tmp_path: Path):
    runner = BwrapSandboxRunner(tmp_path)
    res = runner.run_command(
        "pip install requests; awk -F: '/^ *[a-z0-9]+:/ {print $1}' /proc/net/dev"
    )
    assert _interfaces(res.stdout) == ["lo"]


def test_package_install_policy_allows_network():
    limits = SandboxLimits()
    assert network_allowed("pip install requests", limits) is True
    assert (
        network_allowed("pip install requests; curl http://example.com", limits)
        is False
    )
    assert network_allowed("npm test", limits) is False


def test_allow_network_sees_host_interfaces(tmp_path: Path):
    runner = BwrapSandboxRunner(tmp_path, limits=SandboxLimits(allow_network=True))
    res = runner.run_command("awk -F: '/^ *[a-z0-9]+:/ {print $1}' /proc/net/dev")
    assert res.exit_code == 0, res.stderr
    assert _interfaces(res.stdout) != ["lo"]
