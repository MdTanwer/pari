"""Sign in with an API key or an account token. The token is not printed."""

import json
import os
import time
from pathlib import Path

import pytest

from pari.auth.login import (
    default_model_name,
    resolve_secret,
    sign_in,
    sign_in_hint,
    sign_out,
    status_text,
)
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


def test_no_credential_selects_no_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("PARI_MODEL", raising=False)
    for name in (
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "XAI_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    assert default_model_name(AuthStore(tmp_path / "auth.json")) is None


def test_latest_sign_in_is_the_default_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("PARI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    store = AuthStore(tmp_path / "auth.json")
    sign_in("openai", "sk-proj-0123456789abcdef", "api_key", store)
    sign_in("deepseek", "sk-0123456789abcdefxyz", "api_key", store)
    assert default_model_name(store) == "deepseek-chat"
    sign_in("openai", "sk-proj-0123456789abcdef", "api_key", store)
    assert default_model_name(store) == "gpt-4o"
    monkeypatch.setenv("PARI_MODEL", "claude-3-7-sonnet-20250219")
    assert default_model_name(store) == "claude-3-7-sonnet-20250219"


def test_empty_and_unknown_sign_in_are_rejected(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    sign_in("grok", "acct-token", "account", store)
    with pytest.raises(ValueError, match="empty"):
        sign_in("openai", "   ", "api_key", store)
    with pytest.raises(ValueError, match="API key or an account"):
        sign_in("openai", "sk-proj-0123456789abcdef", "password", store)
    with pytest.raises(ValueError, match="Unknown provider"):
        sign_in("radius", "sk-proj-0123456789abcdef", "api_key", store)
    assert list(store.load()) == ["grok"]


def test_api_key_shape_is_rejected_without_replacing_a_saved_login(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    sign_in("grok", "acct-token", "account", store)
    rejected = (
        ("openai", "sk-proj-0123 456789abcdef", "spaces"),
        ("openai", "sk-short", "too short"),
        ("openai", "sk-proj-0123456789abcdef!", "not allowed"),
        ("openai", "sk-or-v1-0123456789abcd", "OpenRouter"),
        ("openai", "xai-0123456789abcdefxx", "Grok"),
        ("grok", "sk-proj-0123456789abcdef", "OpenAI or DeepSeek"),
    )
    for provider, secret, match in rejected:
        with pytest.raises(ValueError, match=match):
            sign_in(provider, secret, "api_key", store)
    assert store.load()["grok"]["secret"] == "acct-token"
    assert "openai" not in store.load()


def test_account_sign_in_stores_refresh_fields_and_strips_the_secret(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    message = sign_in(
        "openai",
        "  access-token  ",
        "account",
        store,
        extra={
            "refresh": " refresh-token ",
            "client_id": " client ",
            "expires": 1_700_000_000_000,
            "note": "leave this out",
        },
    )
    assert message == "Signed in to OpenAI with an account."
    assert "access-token" not in message
    assert "refresh-token" not in message
    row = store.load()["openai"]
    assert row["secret"] == "access-token"
    assert row["refresh"] == "refresh-token"
    assert row["client_id"] == "client"
    assert row["expires"] == 1_700_000_000_000
    assert "note" not in row


def test_sign_out_of_a_missing_provider_leaves_the_file(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    sign_in("openai", "sk-proj-0123456789abcdef", "api_key", store)
    assert sign_out("grok", store) == "Grok is not signed in."
    assert store.load()["openai"]["secret"] == "sk-proj-0123456789abcdef"


def test_environment_credential_wins_over_a_saved_secret(tmp_path: Path, monkeypatch):
    store = AuthStore(tmp_path / "auth.json")
    sign_in("openai", "sk-proj-0123456789abcdef", "api_key", store)
    monkeypatch.setenv("OPENAI_API_KEY", "from-the-environment")
    assert resolve_secret(get_info("openai"), store) == "from-the-environment"
    assert store.load()["openai"]["secret"] == "sk-proj-0123456789abcdef"


def test_expired_openai_account_is_refreshed(tmp_path: Path, monkeypatch):
    store = AuthStore(tmp_path / "auth.json")
    store.save(_openai_row("old-access", "old-refresh", 1))

    def fake_form(url, fields):
        assert fields["grant_type"] == "refresh_token"
        assert fields["refresh_token"] == "old-refresh"
        assert fields["client_id"] == "issued-client"
        return 200, {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "scope": "openid chatgpt.tokens.use.direct",
        }

    monkeypatch.setattr("pari.auth.account.post_form", fake_form)
    assert resolve_secret(get_info("openai"), store) == "new-access"
    saved = store.load()["openai"]
    assert saved["secret"] == "new-access"
    assert saved["refresh"] == "new-refresh"


def test_a_failed_refresh_keeps_the_saved_secret(tmp_path: Path, monkeypatch):
    store = AuthStore(tmp_path / "auth.json")
    store.save(_openai_row("old-access", "old-refresh", 1))

    def fake_form(url, fields):
        return 401, {"error": "invalid_grant"}

    monkeypatch.setattr("pari.auth.account.post_form", fake_form)
    with pytest.raises(RuntimeError, match="OpenAI token refresh"):
        resolve_secret(get_info("openai"), store)
    assert store.load()["openai"]["secret"] == "old-access"


def test_a_current_account_token_is_not_refreshed(tmp_path: Path, monkeypatch):
    store = AuthStore(tmp_path / "auth.json")
    later = int(time.time() * 1000) + 60_000
    store.save(_openai_row("still-good", "refresh-token", later))

    def fake_form(url, fields):
        raise AssertionError(url)

    monkeypatch.setattr("pari.auth.account.post_form", fake_form)
    assert resolve_secret(get_info("openai"), store) == "still-good"


def test_deepseek_cannot_refresh_an_expired_account(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    store.save(
        {
            "deepseek": {
                "method": "account",
                "secret": "old-access",
                "refresh": "old-refresh",
                "expires": 1,
            }
        }
    )
    with pytest.raises(RuntimeError, match="Sign in to DeepSeek again"):
        resolve_secret(get_info("deepseek"), store)
    assert store.load()["deepseek"]["secret"] == "old-access"


def test_a_saved_row_without_a_secret_is_ignored(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    store.save({"openai": {"method": "api_key"}})
    assert resolve_secret(get_info("openai"), store) is None
    assert "openai: not signed in" in status_text(store)


def test_sign_in_hint_names_the_command():
    hint = sign_in_hint(get_info("openai"))
    assert "pari-cli login openai --api-key" in hint
    assert "pari-cli login openai --account" in hint


def test_deepseek_account_sign_in_is_rejected(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    with pytest.raises(ValueError, match="no account sign-in"):
        sign_in("deepseek", "ds-account", "account", store)
    assert store.load() == {}
    hint = sign_in_hint(get_info("deepseek"))
    assert hint == "Sign in to DeepSeek: pari-cli login deepseek --api-key <key>."
    assert "--account" not in hint


def _openai_row(secret: str, refresh: str, expires: int) -> dict:
    return {
        "openai": {
            "method": "account",
            "secret": secret,
            "refresh": refresh,
            "client_id": "issued-client",
            "expires": expires,
        }
    }
