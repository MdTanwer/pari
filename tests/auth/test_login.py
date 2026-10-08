"""Sign in with an API key or an account token. The token is not printed."""

import json
import os
from pathlib import Path

import pytest

from pari.auth.login import resolve_secret, sign_in, sign_out, status_text
from pari.auth.providers import get_info
from pari.auth.store import AuthStore
from pari.cli import main
from pari.providers import get_provider
from pari.providers.openai import OpenAIProvider


def test_api_key_and_account_are_stored_without_being_shown(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    assert "API key" in sign_in("openai", "sk-proj-0123456789abcdef", "api_key", store)
    assert "account" in sign_in("grok", "acct-token", "account", store)
    text = status_text(store)
    assert "openai: signed in with an API key" in text
    assert "grok: signed in with an account" in text
    assert "sk-proj-0123456789abcdef" not in text
    assert "acct-token" not in text
    mode = os.stat(store.path).st_mode & 0o777
    assert mode == 0o600
    saved = json.loads(store.path.read_text(encoding="utf-8"))
    assert saved["openai"]["secret"] == "sk-proj-0123456789abcdef"


def test_sign_out_removes_only_that_provider(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    sign_in("deepseek", "sk-0123456789abcdefxyz", "api_key", store)
    sign_in("anthropic", "sk-ant-0123456789abcdef", "api_key", store)
    assert "Signed out" in sign_out("deepseek", store)
    assert resolve_secret(get_info("deepseek"), store) is None
    assert resolve_secret(get_info("anthropic"), store) == "sk-ant-0123456789abcdef"


def test_saved_key_selects_openai(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PARI_AUTH_FILE", str(tmp_path / "auth.json"))
    sign_in("openai", "sk-proj-saved0123456789ab", "api_key")
    provider = get_provider("gpt-4o")
    assert isinstance(provider, OpenAIProvider)
    assert provider.api_key == "sk-proj-saved0123456789ab"
    assert provider.base_url == "https://api.openai.com/v1/chat/completions"


def test_wrong_api_key_format_is_rejected(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    with pytest.raises(ValueError, match="start with sk-ant-"):
        sign_in("anthropic", "not-a-key", "api_key", store)
    with pytest.raises(ValueError, match="belongs to Anthropic"):
        sign_in("openai", "sk-ant-0123456789abcdef", "api_key", store)
    assert store.load() == {}


def test_cli_login_does_not_print_the_key(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("PARI_AUTH_FILE", str(tmp_path / "auth.json"))
    code = main(["login", "openrouter", "--api-key", "sk-or-v1-0123456789abcd"])
    assert code == 0
    output = capsys.readouterr().out
    assert "OpenRouter" in output
    assert "sk-or-v1-0123456789abcd" not in output
    assert "API key" in output
