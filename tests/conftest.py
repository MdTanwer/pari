"""Shared pytest fixtures."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_session_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests off developer's real system ~/.pari sessions."""
    monkeypatch.setenv("PARI_SESSION_DIR", str(tmp_path / "system_pari" / "sessions"))
