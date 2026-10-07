"""Workspace writes, secret blackout, and read-only mounts."""

import shlex
from pathlib import Path

from pari.sandbox.base import SandboxLimits
from pari.sandbox.dispatcher import get_sandbox_runner


def test_workspace_write_and_outside_path_hidden(tmp_path: Path):
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


def test_secrets_and_git_inside_workspace_are_masked(tmp_path: Path):
    ssh = tmp_path / ".ssh"
    ssh.mkdir()
    (ssh / "id_rsa").write_text("secret-key")
    (tmp_path / ".bashrc").write_text("export LEAK=1")
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

    runner = get_sandbox_runner(tmp_path)
    res = runner.run_command(
        "if grep -q secret-key .ssh/id_rsa 2>/dev/null; then echo ssh_visible; "
        "else echo ssh_hidden; fi; "
        "if grep -q LEAK .bashrc 2>/dev/null; then echo rc_visible; "
        "else echo rc_hidden; fi; "
        "if touch .git/pari-probe 2>/dev/null; then echo git_writable; "
        "else echo git_readonly; fi"
    )
    assert res.exit_code == 0, res.stderr
    assert "ssh_hidden" in res.stdout
    assert "rc_hidden" in res.stdout
    assert "git_readonly" in res.stdout
    assert "ssh_visible" not in res.stdout
    assert not (git_dir / "pari-probe").exists()


def test_system_path_is_read_only(tmp_path: Path):
    probe = Path("/usr/pari-sandbox-probe")
    if probe.exists():
        probe.unlink()
    runner = get_sandbox_runner(tmp_path)
    res = runner.run_command("touch /usr/pari-sandbox-probe")
    assert res.exit_code != 0
    assert not probe.exists()


def test_read_only_workspace_rejects_writes(tmp_path: Path):
    runner = get_sandbox_runner(tmp_path, limits=SandboxLimits(read_only=True))
    res = runner.run_command("touch blocked.txt")
    assert res.exit_code != 0
    assert not (tmp_path / "blocked.txt").exists()
