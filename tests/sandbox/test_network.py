"""Network stays off except for a single package install."""

from pathlib import Path

from pari.sandbox.base import SandboxLimits, network_allowed, scrub_env
from pari.sandbox.bwrap import BwrapSandboxRunner


def test_network_unshared_by_default(tmp_path: Path):
    runner = BwrapSandboxRunner(tmp_path)
    env = scrub_env(home="/tmp")
    assert "--unshare-net" in runner._argv("echo hi", env)

    res = runner.run_command("awk -F: '/^ *[a-z0-9]+:/ {print $1}' /proc/net/dev")
    interfaces = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    assert interfaces == ["lo"]


def test_package_install_may_use_network(tmp_path: Path):
    runner = BwrapSandboxRunner(tmp_path)
    env = scrub_env(home="/tmp")
    assert "--unshare-net" not in runner._argv("pip install requests", env)
    assert "--unshare-net" in runner._argv("pip install requests; curl http://example.com", env)
    assert network_allowed("npm test", SandboxLimits()) is False


def test_allow_network_shares_host_network(tmp_path: Path):
    runner = BwrapSandboxRunner(tmp_path, limits=SandboxLimits(allow_network=True))
    env = scrub_env(home="/tmp")
    assert "--unshare-net" not in runner._argv("echo hi", env)
