"""Published installers pin a release and do not fall back to git main."""

import hashlib
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = ("install.sh", "install.ps1")
_COPIES = (
    "install.sh",
    "install.ps1",
    "website/public/install.sh",
    "website/public/install.ps1",
)


def test_installers_pin_the_release_that_published_them():
    version = _version()
    for relative in _COPIES:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert f'"{version}"' in text
        assert "PARI_INSTALL_FROM_SOURCE" in text
        assert "pari-cli==" in text
        assert "pari.git@v" in text
        assert "git+${REPO_URL}" not in text
        assert 'pari.git"' not in text
        assert "falling back to GitHub" not in text
        assert "uv tool upgrade" not in text
        assert "pipx upgrade" not in text


def test_sha256sums_match_the_scripts_beside_them():
    expected = _checksums()
    assert (ROOT / "SHA256SUMS").read_text(encoding="utf-8") == expected
    public = ROOT / "website" / "public"
    assert (public / "SHA256SUMS").read_text(encoding="utf-8") == expected
    for name in _SCRIPTS:
        assert (public / name).read_bytes() == (ROOT / name).read_bytes()


def _version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    assert isinstance(version, str)
    return version


def _checksums() -> str:
    lines = []
    for name in _SCRIPTS:
        digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    return "\n".join(lines) + "\n"
