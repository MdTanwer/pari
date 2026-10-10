"""A key the provider does not accept is refused before it is saved."""

from functools import partial
from pathlib import Path

import httpx
import pytest

from pari.auth.login import sign_in
from pari.auth.providers import get_info
from pari.auth.store import AuthStore
from pari.auth.verify import verify_api_key
from pari.cli import main


KEY = "sk-proj-0123456789abcdef"


def _transport(status: int, seen: list[httpx.Request] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json={})

    return httpx.MockTransport(handler)


def _unreachable(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("no route", request=request)


def test_an_accepted_key_is_sent_in_the_provider_header():
    seen: list[httpx.Request] = []
    verify_api_key(get_info("openai"), KEY, _transport(200, seen))
    assert seen[0].headers["authorization"] == f"Bearer {KEY}"
    verify_api_key(
        get_info("anthropic"), "sk-ant-0123456789abcdef", _transport(200, seen)
    )
    assert seen[1].headers["x-api-key"] == "sk-ant-0123456789abcdef"
    assert "authorization" not in seen[1].headers


@pytest.mark.parametrize(
    ("transport", "message"),
    [
        (_transport(401), "OpenAI rejected that API key"),
        (_transport(403), "OpenAI rejected that API key"),
        (_transport(500), "could not check the key \\(HTTP 500\\)"),
        (httpx.MockTransport(_unreachable), "Could not reach OpenAI"),
    ],
)
def test_a_key_that_is_not_accepted_is_refused_without_echoing_it(transport, message):
    with pytest.raises(ValueError, match=message) as error:
        verify_api_key(get_info("openai"), KEY, transport)
    assert KEY not in str(error.value)


def test_a_rejected_key_is_not_saved_and_keeps_the_saved_login(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    sign_in("grok", "acct-token", "account", store)
    verify = partial(verify_api_key, transport=_transport(401))
    with pytest.raises(ValueError, match="rejected"):
        sign_in("openai", KEY, "api_key", store, verify=verify)
    assert list(store.load()) == ["grok"]


def test_a_malformed_key_is_refused_before_any_request(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    seen: list[httpx.Request] = []
    verify = partial(verify_api_key, transport=_transport(200, seen))
    with pytest.raises(ValueError, match="start with sk-ant-"):
        sign_in("anthropic", "not-a-key", "api_key", store, verify=verify)
    assert seen == []


def test_an_account_token_is_not_sent_to_the_key_check(tmp_path: Path):
    store = AuthStore(tmp_path / "auth.json")
    seen: list[httpx.Request] = []
    verify = partial(verify_api_key, transport=_transport(401, seen))
    sign_in("grok", "acct-token", "account", store, verify=verify)
    assert seen == []
    assert store.load()["grok"]["secret"] == "acct-token"


def test_cli_login_reports_a_rejected_key_and_saves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    auth_file = tmp_path / "auth.json"
    monkeypatch.setenv("PARI_AUTH_FILE", str(auth_file))

    def reject(info, _key):
        raise ValueError(f"{info.label} rejected that API key. Check it and try again.")

    monkeypatch.setattr("pari.cli.verify_api_key", reject)
    assert main(["login", "openai", "--api-key", KEY]) == 1
    captured = capsys.readouterr()
    assert "OpenAI rejected that API key" in captured.err
    assert KEY not in captured.out + captured.err
    assert not auth_file.exists() or AuthStore(auth_file).load() == {}
