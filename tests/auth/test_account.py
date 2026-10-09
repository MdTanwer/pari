"""Account login stops before a bad callback or device response is stored."""

import socket

import pytest

from pari.auth.account import LoginCancelled, sign_in_account
from pari.auth.store import AuthStore


class _IdleServer:
    def __init__(self, *args, **kwargs):
        self.done = None
        self.code = None
        self.client_id = None
        self.error = None
        self.port = 1455
        self.redirect_uri = ""

    def start(self):
        return None

    def close(self):
        return None


class _Paste:
    def __init__(self, pasted: str):
        self._pasted = pasted

    def show_auth_url(self, url, instructions, prompt, done):
        return self._pasted


def test_blank_deepseek_account_token_cancels(tmp_path):
    store = AuthStore(tmp_path / "auth.json")

    class UI:
        def read_line(self, prompt):
            return "  "

    with pytest.raises(LoginCancelled):
        sign_in_account("deepseek", UI(), store)
    assert store.load() == {}


def test_anthropic_account_cancel_stores_nothing(tmp_path):
    store = AuthStore(tmp_path / "auth.json")

    class UI:
        def choose(self, title, options):
            assert "Browser login" in options
            assert "Copy code login" in options
            return None

    with pytest.raises(LoginCancelled):
        sign_in_account("anthropic", UI(), store)
    assert store.load() == {}


def test_openai_paste_with_the_wrong_state_is_not_saved(tmp_path, monkeypatch):
    store = AuthStore(tmp_path / "auth.json")
    monkeypatch.setattr("pari.auth.account.CallbackServer", _IdleServer)
    pasted = (
        "http://127.0.0.1:1455/auth/callback"
        "?code=auth-code&state=wrong&client_id=issued"
    )
    with pytest.raises(ValueError, match="state mismatch"):
        sign_in_account("openai", _Paste(pasted), store)
    assert "openai" not in store.load()


def test_openai_paste_must_use_the_fixed_redirect(tmp_path, monkeypatch):
    store = AuthStore(tmp_path / "auth.json")
    monkeypatch.setattr("pari.auth.account.CallbackServer", _IdleServer)
    pasted = "https://evil.example/callback?code=auth-code&state=wrong&client_id=c"
    with pytest.raises(ValueError, match="127.0.0.1:1455/auth/callback"):
        sign_in_account("openai", _Paste(pasted), store)
    assert "openai" not in store.load()


def test_openai_login_stops_when_the_callback_port_is_taken(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 1455))
    except OSError:
        sock.close()
        pytest.skip("port 1455 is already in use")

    class UI:
        def show_auth_url(self, url, instructions, prompt, done):
            raise AssertionError("callback server started")

    try:
        with pytest.raises(RuntimeError, match="Port 1455 is in use"):
            sign_in_account("openai", UI(), store)
        assert store.load() == {}
    finally:
        sock.close()


def test_grok_rejects_a_non_https_verification_page(tmp_path, monkeypatch):
    store = AuthStore(tmp_path / "auth.json")

    def fake_form(url, fields):
        return 200, {
            "device_code": "device-1",
            "user_code": "ABCD-EFGH",
            "verification_uri": "http://auth.x.ai/device",
            "expires_in": 60,
            "interval": 1,
        }

    monkeypatch.setattr("pari.auth.account.post_form", fake_form)

    class UI:
        def show_device(self, url, user_code):
            raise AssertionError(url)

        def sleep(self, seconds):
            return False

    with pytest.raises(RuntimeError, match="Untrusted verification URI"):
        sign_in_account("grok", UI(), store)
    assert store.load() == {}


def test_grok_denial_is_not_stored(tmp_path, monkeypatch):
    store = AuthStore(tmp_path / "auth.json")
    calls = {"n": 0}

    def fake_form(url, fields):
        calls["n"] += 1
        if calls["n"] == 1:
            return 200, {
                "device_code": "device-1",
                "user_code": "ABCD-EFGH",
                "verification_uri": "https://auth.x.ai/device",
                "expires_in": 60,
                "interval": 0,
            }
        return 400, {"error": "access_denied"}

    monkeypatch.setattr("pari.auth.account.post_form", fake_form)

    class UI:
        def show_device(self, url, user_code):
            return None

        def sleep(self, seconds):
            return False

    with pytest.raises(RuntimeError, match="was denied"):
        sign_in_account("grok", UI(), store)
    assert store.load() == {}
