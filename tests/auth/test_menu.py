"""Login menus follow the account / API key picker. Radius is not offered."""

import os
import pty
import threading
import time
import tty
import urllib.error
import urllib.parse
import urllib.request

from pari.auth.account import CallbackServer, openai_authorize_url
from pari.auth.interactive import read_menu_key, run_login, run_logout
from pari.auth.login import sign_in
from pari.auth.menu import (
    LOGOUT_TITLE,
    METHOD_ACCOUNT,
    METHOD_API_KEY,
    NAV_HINT,
    ChoiceMenu,
    ProviderChoice,
    ProviderMenu,
    provider_rows,
    signed_in_rows,
)
from pari.auth.store import AuthStore
from pari.cli import main


def test_down_arrow_moves_the_method_menu():
    menu = ChoiceMenu(
        "Select authentication method:",
        [METHOD_ACCOUNT, METHOD_API_KEY],
    )
    key, rest = read_menu_key(-1, b"\x1b[I\x1b[B", None)
    assert key == "down"
    assert rest == b""
    menu.on_key(key)
    assert menu.lines()[3] == "→ Sign in with an API key"


def test_terminal_arrow_is_down_not_cancel():
    master, slave = pty.openpty()
    try:
        tty.setraw(slave)
        os.write(master, b"\x1b")

        def finish():
            time.sleep(0.02)
            os.write(master, b"[B")

        threading.Thread(target=finish).start()
        key, rest = read_menu_key(slave, b"", 1)
        assert key == "down"
        assert rest == b""
    finally:
        os.close(master)
        os.close(slave)


def test_method_menu_lists_account_and_api_key():
    menu = ChoiceMenu(
        "Select authentication method:",
        [METHOD_ACCOUNT, METHOD_API_KEY],
    )
    lines = menu.lines()
    assert lines[0] == "Select authentication method:"
    assert lines[2] == "→ Sign in with an account"
    assert lines[3] == "  Sign in with an API key"
    assert lines[-1] == NAV_HINT
    assert "Radius" not in "\n".join(lines)
    menu.on_key("down")
    assert menu.on_key("enter") == METHOD_API_KEY


def test_api_key_menu_has_a_search_line_and_hides_the_secret(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    sign_in("openai", "sk-proj-hidden0123456789ab", "api_key", store)
    rows = provider_rows("api_key", store)
    menu = ProviderMenu(rows, search=True, title="Select provider to configure:")
    text = "\n".join(menu.lines())
    assert text.startswith("Select provider to configure:\n\n> ")
    assert "→ Anthropic • not configured" in text
    assert "OpenAI ✓ configured" in text
    assert "sk-proj-hidden0123456789ab" not in text
    menu.on_key("g")
    menu.on_key("r")
    assert [row.name for row in menu.visible()] == ["Grok"]
    assert menu.on_key("enter") == "grok"


def test_account_menu_shows_a_saved_api_key_as_the_other_method(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    sign_in("openai", "sk-proj-hidden0123456789ab", "api_key", store)
    menu = ProviderMenu(provider_rows("account", store), search=False)
    text = "\n".join(menu.lines())
    assert not text.startswith("Select provider")
    assert "> " not in text.splitlines()[0]
    assert "→ Anthropic • not configured" in text
    assert "OpenAI • API key configured" in text
    assert "sk-proj-hidden0123456789ab" not in text


class _Scripted:
    def __init__(self, method, provider, secret="", paste="", choices=None):
        self._method = method
        self._provider = provider
        self._secret = secret
        self._paste = paste
        self._choices = choices or {}
        self.rows = []
        self.shown = []
        self.device = None

    def choose(self, title, options):
        if title.startswith("Select authentication method"):
            assert METHOD_ACCOUNT in options
            assert METHOD_API_KEY in options
            assert all("Radius" not in option for option in options)
            return self._method
        return self._choices.get(title)

    def choose_provider(self, method, rows):
        self.rows = rows
        return self._provider

    def read_secret(self, prompt):
        return self._secret

    def show_error(self, message):
        self.error = message

    def read_line(self, prompt):
        return self._secret

    def show_auth_url(self, url, instructions, prompt, done):
        self.shown.append((url, instructions, prompt))
        if self._paste == "from-url":
            return _paste_from_authorize_url(url)
        return self._paste or None

    def show_device(self, url, user_code):
        self.device = (url, user_code)

    def sleep(self, seconds):
        return False


def _paste_from_authorize_url(url: str) -> str:
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    state = query["state"][0]
    redirect = query["redirect_uri"][0]
    return f"{redirect}?code=auth-code&state={state}&client_id=issued-client"


def test_api_key_login_stores_the_key_without_printing_it(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    ui = _Scripted(METHOD_API_KEY, "deepseek", secret="sk-0123456789abcdefxyz")
    message = run_login(ui, store)
    assert message == "Signed in to DeepSeek with an API key."
    assert "sk-0123456789abcdefxyz" not in message
    assert store.load()["deepseek"]["secret"] == "sk-0123456789abcdefxyz"
    assert [row.name for row in ui.rows] == [
        "Anthropic",
        "DeepSeek",
        "Grok",
        "OpenAI",
        "OpenRouter",
    ]


def test_openai_account_login_uses_the_browser_url(tmp_path, monkeypatch):
    store = AuthStore(tmp_path / "auth.json")

    class FakeServer:
        def __init__(self, *args, **kwargs):
            self.done = threading.Event()
            self.code = None
            self.client_id = None
            self.error = None
            self.port = 1455
            self.redirect_uri = ""

        def start(self):
            return None

        def close(self):
            return None

    def fake_form(url, fields):
        assert fields["code"] == "auth-code"
        assert fields["client_id"] == "issued-client"
        return 200, {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
            "id_token": "id-token",
            "scope": "openid chatgpt.tokens.use.direct",
        }

    monkeypatch.setattr("pari.auth.account.CallbackServer", FakeServer)
    monkeypatch.setattr("pari.auth.account.post_form", fake_form)
    ui = _Scripted(METHOD_ACCOUNT, "openai", paste="from-url")
    message = run_login(ui, store)
    assert message == "Signed in to OpenAI with an account."
    assert "access-token" not in message
    url, instructions, _prompt = ui.shown[0]
    assert url.startswith("https://auth.openai.com/api/accounts/authorize?")
    assert "client_id=dynamic_agent_client" in url
    assert "agent_name_hint=PARI" in url
    assert "callback does not complete" in instructions
    saved = store.load()["openai"]
    assert saved["secret"] == "access-token"
    assert saved["client_id"] == "issued-client"
    assert saved["method"] == "account"


def test_grok_account_login_shows_the_device_code(tmp_path, monkeypatch):
    store = AuthStore(tmp_path / "auth.json")

    def fake_form(url, fields):
        if url.endswith("/device/code"):
            return 200, {
                "device_code": "device-1",
                "user_code": "ABCD-EFGH",
                "verification_uri": "https://auth.x.ai/device",
                "expires_in": 60,
                "interval": 0,
            }
        return 200, {
            "access_token": "grok-access",
            "refresh_token": "grok-refresh",
            "expires_in": 3600,
        }

    monkeypatch.setattr("pari.auth.account.post_form", fake_form)
    ui = _Scripted(METHOD_ACCOUNT, "grok")
    message = run_login(ui, store)
    assert message == "Signed in to Grok with an account."
    assert ui.device == ("https://auth.x.ai/device", "ABCD-EFGH")
    assert "grok-access" not in message
    assert store.load()["grok"]["secret"] == "grok-access"


def test_deepseek_is_absent_from_the_account_menu(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    rows = provider_rows("account", store)
    assert "deepseek" not in [row.id for row in rows]
    assert "deepseek" in [row.id for row in provider_rows("api_key", store)]


def test_deepseek_account_choice_does_not_ask_for_a_token(tmp_path):
    store = AuthStore(tmp_path / "auth.json")

    class UI:
        def __init__(self):
            self.errors: list[str] = []
            self.asked = False

        def choose(self, title, options):
            if self.errors:
                return None
            return METHOD_ACCOUNT

        def read_line(self, prompt):
            self.asked = True
            return "token"

        def read_secret(self, prompt):
            self.asked = True
            return "token"

        def show_error(self, message):
            self.errors.append(message)

    ui = UI()
    assert run_login(ui, store, provider_id="deepseek") == ""
    assert ui.asked is False
    assert "no account sign-in" in ui.errors[0]
    assert store.load() == {}


def test_authorize_url_uses_the_fixed_redirect():
    url = openai_authorize_url(
        "12345678-1234-1234-1234-123456789abc",
        "challenge",
        "state-1",
        "nonce-1",
    )
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A1455%2Fauth%2Fcallback" in url
    assert "code_challenge=challenge" in url
    assert "code_challenge_method=S256" in url


def test_bad_key_is_reported_and_not_saved(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    answers = ["not-a-key", "sk-ant-0123456789abcdef"]

    class Ask:
        def __init__(self):
            self.errors = []

        def choose(self, title, options):
            return METHOD_API_KEY

        def choose_provider(self, method, rows):
            return "anthropic"

        def read_secret(self, prompt):
            return answers.pop(0)

        def show_error(self, message):
            self.errors.append(message)

    ui = Ask()
    message = run_login(ui, store)
    assert "start with sk-ant-" in ui.errors[0]
    assert message == "Signed in to Anthropic with an API key."
    assert "not-a-key" not in message
    assert store.load()["anthropic"]["secret"] == "sk-ant-0123456789abcdef"


def test_logout_menu_lists_only_saved_sign_ins(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    sign_in("openai", "sk-proj-hidden0123456789ab", "api_key", store)
    sign_in("grok", "acct-hidden", "account", store)
    menu = ProviderMenu(signed_in_rows(store), search=True, title=LOGOUT_TITLE)
    text = "\n".join(menu.lines())
    assert text.startswith("Select provider to logout:")
    assert "→ Grok • account" in text
    assert "OpenAI • API key" in text
    assert "Anthropic" not in text
    assert "sk-proj-hidden0123456789ab" not in text
    assert "acct-hidden" not in text


def test_logout_removes_only_the_chosen_provider(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    sign_in("openai", "sk-proj-hidden0123456789ab", "api_key", store)
    sign_in("grok", "acct-hidden", "account", store)

    class Picker:
        def choose_provider(self, method, rows):
            assert method == "logout"
            assert [row.id for row in rows] == ["grok", "openai"]
            return "openai"

    message = run_logout(Picker(), store)
    assert message == "Signed out of OpenAI."
    assert "sk-proj-hidden0123456789ab" not in message
    assert "openai" not in store.load()
    assert store.load()["grok"]["secret"] == "acct-hidden"


def test_logout_with_no_saved_sign_in(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    assert run_logout(object(), store) == "No saved sign-in to remove."


def test_cli_logout_removes_one_provider(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PARI_AUTH_FILE", str(tmp_path / "auth.json"))
    sign_in("openrouter", "sk-or-v1-0123456789abcd", "api_key")
    code = main(["logout", "openrouter"])
    assert code == 0
    output = capsys.readouterr().out
    assert "Signed out of OpenRouter." in output
    assert "sk-or-v1-0123456789abcd" not in output
    assert "openrouter" not in AuthStore(tmp_path / "auth.json").load()


def test_search_types_letters_and_cancel_leaves_the_login(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    menu = ProviderMenu(provider_rows("api_key", store), search=True)
    menu.on_key("j")
    assert menu.query == "j"
    assert "No matching providers" in "\n".join(menu.lines())
    menu.on_key("backspace")
    assert menu.query == ""
    assert menu.on_key("cancel") == "cancel"

    plain = ProviderMenu(provider_rows("account", store), search=False)
    plain.on_key("j")
    assert plain.lines()[1] == "→ Grok • not configured"

    class Cancel:
        def choose(self, title, options):
            return None

    assert run_login(Cancel(), store) == ""


def test_provider_menu_windows_a_long_list():
    rows = [
        ProviderChoice(f"p{index}", f"Provider {index}", " • not configured")
        for index in range(10)
    ]
    menu = ProviderMenu(rows, search=False)
    for _ in range(9):
        menu.on_key("down")
    text = "\n".join(menu.lines())
    assert "→ Provider 9 • not configured" in text
    assert "Provider 0 • not configured" not in text
    assert "(10/10)" in text


def test_logout_cancel_keeps_the_saved_sign_in(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    sign_in("openai", "sk-proj-hidden0123456789ab", "api_key", store)

    class Picker:
        def choose_provider(self, method, rows):
            return None

    assert run_logout(Picker(), store) == ""
    assert store.load()["openai"]["secret"] == "sk-proj-hidden0123456789ab"


def test_callback_records_the_code_and_ignores_a_bad_state():
    server = CallbackServer(
        "127.0.0.1",
        0,
        "/auth/callback",
        "",
        "state-1",
        "OpenAI",
        True,
    )
    server.start()
    try:
        base = f"http://127.0.0.1:{server.port}/auth/callback"
        try:
            urllib.request.urlopen(f"{base}?code=nope&state=other&client_id=x")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
        try:
            urllib.request.urlopen(f"{base}?error=%3Cscript%3E&state=state-1")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            assert exc.code == 400
            assert "<script>" not in body
            assert "&lt;script&gt;" in body
        assert server.code is None
        urllib.request.urlopen(f"{base}?code=abc&state=state-1&client_id=issued")
        assert server.done.wait(2)
        assert server.code == "abc"
        assert server.client_id == "issued"
    finally:
        server.close()
