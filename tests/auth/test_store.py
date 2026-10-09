"""The auth file is private, and a bad file is not treated as a sign-in."""

import os
from pathlib import Path

import pytest

from pari.auth.store import AuthStore


def test_missing_auth_file_loads_as_empty(tmp_path: Path):
    assert AuthStore(tmp_path / "missing.json").load() == {}


def test_load_rejects_a_file_that_is_not_an_object(tmp_path: Path):
    path = tmp_path / "auth.json"
    store = AuthStore(path)
    path.write_text("[1]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not valid JSON"):
        store.load()
    path.write_text("{", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not valid JSON"):
        store.load()


def test_save_round_trip_is_private(tmp_path: Path):
    store = AuthStore(tmp_path / "private" / "auth.json")
    store.save({"openai": {"secret": "sk-test"}})
    assert store.load() == {"openai": {"secret": "sk-test"}}
    file_mode = os.stat(store.path).st_mode & 0o777
    dir_mode = os.stat(store.path.parent).st_mode & 0o777
    assert file_mode == 0o600
    assert dir_mode == 0o700


def test_auth_path_follows_the_environment(tmp_path: Path, monkeypatch):
    custom = tmp_path / "custom.json"
    monkeypatch.setenv("PARI_AUTH_FILE", str(custom))
    assert AuthStore().path == custom
    monkeypatch.setenv("PARI_AUTH_FILE", "")
    assert AuthStore().path == Path.home() / ".pari" / "auth.json"
    monkeypatch.delenv("PARI_AUTH_FILE")
    assert AuthStore().path == Path.home() / ".pari" / "auth.json"
