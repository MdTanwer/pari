"""macOS Seatbelt profile generation."""

from pathlib import Path

from pari.sandbox.seatbelt import render_seatbelt_profile


def test_profile_uses_absolute_secret_paths(tmp_path: Path):
    home = Path("/Users/dev")
    profile = render_seatbelt_profile(
        tmp_path, home, allow_network=False, read_only=False
    )
    assert "~" not in profile
    assert str(home / ".ssh") in profile
    assert str(home / ".config") in profile
    assert "(deny network-inbound)" in profile
    assert "network-outbound" not in profile
    assert str(tmp_path) in profile


def test_read_only_profile_denies_workspace_writes(tmp_path: Path):
    online = render_seatbelt_profile(
        tmp_path, Path("/Users/dev"), allow_network=True, read_only=True
    )
    assert "network-outbound" in online
    assert "file-write*" not in online.split("(deny file-write*")[0]
