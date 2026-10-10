"""Account login stops before a bad callback or device response is stored."""

import socket

import pytest

from pari.auth.account import (
    LoginCancelled,
    _anthropic_fields,
    _anthropic_url,
    _device_id,
    _exchange_openrouter,
    _expires_at,
    _first,
    _html,
    _http_error,
    _https_uri,
    _json_body,
    _openai_fields,
    _parse_paste,
    _pkce,
    _refresh_anthropic,
    _refresh_grok,
    _refresh_openai,
    _required,
    _token_fields,
    _uuid_ok,
    openai_authorize_url,
    sign_in_account,
)
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


def test_deepseek_account_does_not_ask_for_a_token(tmp_path):
    store = AuthStore(tmp_path / "auth.json")

    class UI:
        def read_line(self, prompt):
            raise AssertionError(prompt)

    with pytest.raises(ValueError, match="no account sign-in"):
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


def test_openai_authorize_url_requires_a_uuid_device_id():
    with pytest.raises(ValueError, match="device id"):
        openai_authorize_url("not-a-uuid", "challenge", "state", "nonce")


def test_openai_authorize_url_encodes_the_pkce_and_state():
    url = openai_authorize_url(
        "00000000-0000-4000-8000-000000000000",
        "challenge!",
        "state value",
        "nonce value",
    )
    assert url.startswith("https://auth.openai.com/api/accounts/authorize?")
    assert "code_challenge=challenge%21" in url
    assert "code_challenge_method=S256" in url
    assert "state=state+value" in url
    assert "nonce=nonce+value" in url
    assert "redirect_uri=" in url


def test_pkce_produces_a_valid_base64url_challenge():
    verifier, challenge = _pkce()
    assert len(verifier) >= 43
    assert challenge
    assert "=" not in challenge
    assert "+" not in challenge
    assert "/" not in challenge


def test_uuid_ok_accepts_only_valid_uuids():
    assert _uuid_ok("00000000-0000-4000-8000-000000000000")
    assert _uuid_ok("FFFFFFFF-FFFF-4FFF-8FFF-FFFFFFFFFFFF".lower())
    assert not _uuid_ok("00000000-0000-4000-8000-00000000000")
    assert not _uuid_ok("")
    assert not _uuid_ok("12345")
    assert not _uuid_ok("gggggggg-gggg-gggg-gggg-gggggggggggg")


def test_device_id_writes_a_stable_uuid_to_the_store(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    first = _device_id(store)
    assert _uuid_ok(first)
    assert store.load()["_device"] == first
    assert _device_id(store) == first


def test_device_id_reuses_an_existing_valid_device(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    store.save({"_device": "00000000-0000-4000-8000-000000000000"})
    assert _device_id(store) == "00000000-0000-4000-8000-000000000000"


def test_required_rejects_missing_and_wrong_types():
    with pytest.raises(RuntimeError, match="access_token"):
        _required({}, "access_token")
    with pytest.raises(RuntimeError, match="access_token"):
        _required({"access_token": 42}, "access_token")
    with pytest.raises(RuntimeError, match="access_token"):
        _required({"access_token": ""}, "access_token")
    assert _required({"access_token": "abc"}, "access_token") == "abc"


def test_token_fields_uses_previous_refresh_when_absent():
    fields = _token_fields(
        {"access_token": "a", "refresh_token": "keep", "expires_in": 10},
        previous="old",
    )
    assert fields["access"] == "a"
    assert fields["refresh"] == "keep"

    fields = _token_fields(
        {"access_token": "a", "expires_in": 10},
        previous="old",
    )
    assert fields["refresh"] == "old"


def test_token_fields_rejects_a_refresh_with_no_fallback():
    with pytest.raises(RuntimeError, match="refresh_token"):
        _token_fields({"access_token": "a"}, previous="")


def test_token_fields_defaults_expires_when_missing():
    fields = _token_fields(
        {"access_token": "a", "refresh_token": "r"},
        previous="",
    )
    assert isinstance(fields["expires"], int)
    assert fields["expires"] > 0


def test_openai_fields_requires_the_direct_scope():
    with pytest.raises(RuntimeError, match="chatgpt.tokens.use.direct"):
        _openai_fields(
            {"access_token": "a", "refresh_token": "r", "scope": "openid profile"},
            "client",
        )
    fields = _openai_fields(
        {
            "access_token": "a",
            "refresh_token": "r",
            "scope": "openid chatgpt.tokens.use.direct",
        },
        "client",
    )
    assert fields["client_id"] == "client"
    assert fields["access"] == "a"


def test_anthropic_fields_reads_access_refresh_and_expiry():
    fields = _anthropic_fields(
        {"access_token": "a", "refresh_token": "r", "expires_in": 3600}
    )
    assert fields["access"] == "a"
    assert fields["refresh"] == "r"
    assert fields["client_id"] == ""
    assert isinstance(fields["expires"], int)


def test_expires_at_rejects_bad_values():
    for bad in ("10", None, True, 0, -5):
        with pytest.raises(RuntimeError, match="expires_in"):
            _expires_at(bad, 60)
    assert _expires_at(3600, 60) > 0


def test_parse_paste_reads_a_bare_code():
    code, client = _parse_paste("auth-code", "", None)
    assert code == "auth-code"
    assert client is None


def test_parse_paste_accepts_a_plain_query_string():
    code, client = _parse_paste("code=auth-code&client_id=issued", "", None)
    assert code == "auth-code"
    assert client == "issued"


def test_parse_paste_rejects_empty_input():
    with pytest.raises(ValueError, match="callback URL"):
        _parse_paste("   ", "", None)


def test_parse_paste_rejects_a_state_mismatch():
    with pytest.raises(ValueError, match="state mismatch"):
        _parse_paste("code=auth-code&state=wrong", "", "expected")


def test_parse_paste_rejects_a_foreign_redirect():
    with pytest.raises(ValueError, match="must start with"):
        _parse_paste(
            "https://evil.example/cb?code=auth-code",
            "http://127.0.0.1:1455/auth/callback",
            None,
        )


def test_parse_paste_rejects_an_error_response():
    with pytest.raises(ValueError, match="access_denied"):
        _parse_paste("error=access_denied", "", None)


def test_parse_paste_rejects_a_missing_code():
    with pytest.raises(ValueError, match="authorization code"):
        _parse_paste("state=ok", "", None)


def test_https_uri_rejects_non_https():
    with pytest.raises(RuntimeError, match="Untrusted"):
        _https_uri(None)
    with pytest.raises(RuntimeError, match="Untrusted"):
        _https_uri("http://auth.x.ai/device")
    with pytest.raises(RuntimeError, match="Untrusted"):
        _https_uri("not a url")
    assert _https_uri("https://auth.x.ai/device") == "https://auth.x.ai/device"


def test_json_body_rejects_non_object_and_non_json():
    with pytest.raises(RuntimeError, match="not a JSON object"):
        _json_body(b'["a", "b"]')
    with pytest.raises(RuntimeError, match="not JSON"):
        _json_body(b"not json")
    assert _json_body(b'{"a": 1}') == {"a": 1}
    assert _json_body(b"") == {}


def test_http_error_formats_detail_and_falls_back():
    assert _http_error("Boom", 400, {"error_description": "nope"}) == (
        "Boom failed (HTTP 400): nope."
    )
    assert (
        _http_error("Boom", 400, {"error": "nope"}) == "Boom failed (HTTP 400): nope."
    )
    assert _http_error("Boom", 400, {"message": "nope"}) == (
        "Boom failed (HTTP 400): nope."
    )
    assert _http_error("Boom", 400, {}) == "Boom failed (HTTP 400)."


def test_first_takes_the_first_non_empty_value():
    assert _first({"code": ["a", "b"]}, "code") == "a"
    assert _first({"code": [""]}, "code") is None
    assert _first({}, "code") is None


def test_html_escapes_reserved_characters():
    assert _html('<a href="x">&</a>') == '&lt;a href="x"&gt;&amp;&lt;/a&gt;'


def test_anthropic_url_includes_pkce_and_state():
    url = _anthropic_url("challenge", "state", "http://localhost:1/callback")
    assert url.startswith("https://claude.ai/oauth/authorize?")
    assert "code_challenge=challenge" in url
    assert "code_challenge_method=S256" in url
    assert "state=state" in url


def test_refresh_openai_rejects_missing_client_id():
    with pytest.raises(RuntimeError, match="again"):
        _refresh_openai("refresh", "")


def test_refresh_openai_requires_the_direct_scope(monkeypatch):
    def fake_form(url, fields):
        assert fields["grant_type"] == "refresh_token"
        assert fields["client_id"] == "client"
        return 200, {
            "access_token": "a",
            "refresh_token": "r",
            "scope": "openid",
        }

    monkeypatch.setattr("pari.auth.account.post_form", fake_form)
    with pytest.raises(RuntimeError, match="chatgpt.tokens.use.direct"):
        _refresh_openai("refresh", "client")


def test_refresh_openai_succeeds(monkeypatch):
    def fake_form(url, fields):
        return 200, {
            "access_token": "a",
            "refresh_token": "r",
            "scope": "chatgpt.tokens.use.direct",
        }

    monkeypatch.setattr("pari.auth.account.post_form", fake_form)
    fields = _refresh_openai("refresh", "client")
    assert fields["access"] == "a"
    assert fields["client_id"] == "client"


def test_refresh_anthropic_succeeds(monkeypatch):
    def fake_json(url, payload):
        assert payload["grant_type"] == "refresh_token"
        return 200, {"access_token": "a", "refresh_token": "r", "expires_in": 3600}

    monkeypatch.setattr("pari.auth.account.post_json", fake_json)
    fields = _refresh_anthropic("refresh")
    assert fields["access"] == "a"
    assert fields["refresh"] == "r"


def test_refresh_grok_keeps_the_previous_refresh(monkeypatch):
    def fake_form(url, fields):
        assert fields["grant_type"] == "refresh_token"
        return 200, {"access_token": "a"}

    monkeypatch.setattr("pari.auth.account.post_form", fake_form)
    fields = _refresh_grok("refresh")
    assert fields["refresh"] == "refresh"


def test_exchange_openrouter_requires_a_key(monkeypatch):
    def fake_json(url, payload):
        return 200, {}

    monkeypatch.setattr("pari.auth.account.post_json", fake_json)
    with pytest.raises(RuntimeError, match="key"):
        _exchange_openrouter("code", "verifier")


def test_exchange_openrouter_reads_the_key(monkeypatch):
    def fake_json(url, payload):
        assert payload["code"] == "code"
        assert payload["code_verifier"] == "verifier"
        return 200, {"key": "sk-or-123"}

    monkeypatch.setattr("pari.auth.account.post_json", fake_json)
    fields = _exchange_openrouter("code", "verifier")
    assert fields["access"] == "sk-or-123"
    assert fields["refresh"] == ""
