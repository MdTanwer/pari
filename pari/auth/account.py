"""Account sign-in for the five providers.

OpenAI, Anthropic, and OpenRouter open a browser and accept the redirect URL
if the local callback does not finish. Grok uses a device code. DeepSeek has
no browser login, so the account token is pasted. Radius is not a provider.
"""

import base64
import errno
import hashlib
import json
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol

from pari.auth.login import sign_in
from pari.auth.providers import ProviderInfo, get_info
from pari.auth.store import AuthStore


class LoginCancelled(Exception):
    """The user left the sign-in screen."""


class AccountUI(Protocol):
    def choose(self, title: str, options: list[str]) -> str | None: ...

    def read_line(self, prompt: str) -> str | None: ...

    def show_auth_url(
        self,
        url: str,
        instructions: str,
        prompt: str,
        done: threading.Event,
    ) -> str | None: ...

    def show_device(self, url: str, user_code: str) -> None: ...

    def sleep(self, seconds: float) -> bool: ...

    def show_error(self, message: str) -> None: ...


_OPENAI_AUTHORIZE = "https://auth.openai.com/api/accounts/authorize"
_OPENAI_TOKEN = "https://auth.openai.com/api/accounts/oauth/token"
_OPENAI_REDIRECT = "http://127.0.0.1:1455/auth/callback"
_OPENAI_RESOURCE = "https://api.openai.com/v1"
_OPENAI_SCOPE = (
    "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
)
_OPENAI_CLIENT = "dynamic_agent_client"
_DIRECT_SCOPE = "chatgpt.tokens.use.direct"

# Public Claude login client. There is no client secret; PKCE is the check.
_ANTHROPIC_CLIENT = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
_ANTHROPIC_AUTHORIZE = "https://claude.ai/oauth/authorize"
_ANTHROPIC_TOKEN = "https://platform.claude.com/v1/oauth/token"
_ANTHROPIC_SCOPES = (
    "org:create_api_key user:profile user:inference "
    "user:sessions:claude_code user:mcp_servers user:file_upload"
)
_ANTHROPIC_COPY_REDIRECT = "https://platform.claude.com/oauth/code/callback"

_OPENROUTER_AUTHORIZE = "https://openrouter.ai/auth"
_OPENROUTER_TOKEN = "https://openrouter.ai/api/v1/auth/keys"

_XAI_CLIENT = "b1a00492-073a-47ea-816f-4c329264a828"
_XAI_SCOPE = "openid profile email offline_access grok-cli:access api:access"
_XAI_DEVICE = "https://auth.x.ai/oauth2/device/code"
_XAI_TOKEN = "https://auth.x.ai/oauth2/token"

_UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_PASTE = "Complete login in your browser, or paste the final redirect URL here:"
_BROWSER = (
    "Complete sign-in in your browser. If the callback does not complete, "
    "paste the final redirect URL here."
)


def sign_in_account(provider_id: str, ui: AccountUI, store: AuthStore) -> str:
    """Run that provider's account login and store the credential."""
    info = get_info(provider_id)
    if info.id == "deepseek":
        token = ui.read_line("Paste your DeepSeek account token:")
        if not token or not token.strip():
            raise LoginCancelled()
        return sign_in(info.id, token, "account", store)
    if info.id == "openai":
        cred = _login_openai(ui, store)
    elif info.id == "anthropic":
        cred = _login_anthropic(ui)
    elif info.id == "openrouter":
        cred = _login_openrouter(ui)
    elif info.id == "grok":
        cred = _login_grok(ui)
    else:
        raise ValueError(f"No account login for {info.label}.")
    return sign_in(info.id, cred["access"], "account", store, extra=cred)


def refresh_saved(info: ProviderInfo, row: dict, store: AuthStore) -> str:
    """Replace an expired account token. The refresh token is not returned."""
    refresh = str(row.get("refresh") or "")
    if info.id == "openai":
        cred = _refresh_openai(refresh, str(row.get("client_id") or ""))
    elif info.id == "anthropic":
        cred = _refresh_anthropic(refresh)
    elif info.id == "grok":
        cred = _refresh_grok(refresh)
    else:
        raise RuntimeError(f"Sign in to {info.label} again.")
    sign_in(info.id, cred["access"], "account", store, extra=cred)
    return cred["access"]


def openai_authorize_url(
    device_id: str,
    challenge: str,
    state: str,
    nonce: str,
) -> str:
    """Authorize URL for Sign in with ChatGPT. The redirect port is fixed."""
    if not _uuid_ok(device_id):
        raise ValueError("Sign in with an account requires a device id.")
    query = urllib.parse.urlencode(
        {
            "client_id": _OPENAI_CLIENT,
            "agent_name_hint": "PARI",
            "ext_agent_host_id": f"urn:uuid:{device_id.lower()}",
            "response_type": "code",
            "redirect_uri": _OPENAI_REDIRECT,
            "resource": _OPENAI_RESOURCE,
            "scope": _OPENAI_SCOPE,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "nonce": nonce,
        }
    )
    return f"{_OPENAI_AUTHORIZE}?{query}"


def _login_openai(ui: AccountUI, store: AuthStore) -> dict:
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    try:
        server = _listen(
            "127.0.0.1",
            1455,
            "/auth/callback",
            "127.0.0.1",
            state,
            "OpenAI",
            require_client=True,
        )
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise RuntimeError(
                "Port 1455 is in use, probably by an unfinished login. "
                "Cancel that login and try again."
            ) from exc
        raise
    try:
        url = openai_authorize_url(_device_id(store), challenge, state, nonce)
        pasted = ui.show_auth_url(url, _BROWSER, _PASTE, server.done)
        code, client_id = _code_from(server, pasted, _OPENAI_REDIRECT, state)
        if not client_id:
            raise ValueError("Paste the full callback URL from the browser.")
        ui_progress = getattr(ui, "progress", None)
        if ui_progress:
            ui_progress("Exchanging authorization code for tokens...")
        return _exchange_openai(code, verifier, client_id)
    finally:
        server.close()


def _login_anthropic(ui: AccountUI) -> dict:
    choice = ui.choose(
        "Select Anthropic login method:",
        ["Browser login", "Copy code login"],
    )
    if choice is None:
        raise LoginCancelled()
    verifier, challenge = _pkce()
    if choice == "Copy code login":
        return _anthropic_copy_code(ui, verifier, challenge)
    server = _anthropic_server(verifier)
    redirect = (
        server.redirect_uri if server else (f"http://localhost:53692{_callback_path()}")
    )
    try:
        url = _anthropic_url(challenge, verifier, redirect)
        done = server.done if server else threading.Event()
        pasted = ui.show_auth_url(
            url,
            "Complete login in your browser. If the browser is on another "
            "machine, paste the final redirect URL here.",
            "Complete login in your browser, or paste the authorization "
            "code / redirect URL here:",
            done,
        )
        code, _client = _code_from(server, pasted, redirect, verifier)
        return _exchange_anthropic(code, verifier, redirect)
    finally:
        if server:
            server.close()


def _anthropic_copy_code(ui: AccountUI, verifier: str, challenge: str) -> dict:
    url = _anthropic_url(challenge, verifier, _ANTHROPIC_COPY_REDIRECT)
    pasted = ui.show_auth_url(
        url,
        "Complete login in your browser, then copy the code Anthropic "
        "shows and paste it here.",
        "Paste the code Anthropic shows after you sign in:",
        threading.Event(),
    )
    if not pasted:
        raise LoginCancelled()
    code, _client = _parse_paste(pasted, "", verifier)
    return _exchange_anthropic(code, verifier, _ANTHROPIC_COPY_REDIRECT)


def _login_openrouter(ui: AccountUI) -> dict:
    verifier, challenge = _pkce()
    path = f"/oauth/callback/{uuid.uuid4()}"
    server = _listen("127.0.0.1", 0, path, "127.0.0.1", "", "OpenRouter")
    try:
        query = urllib.parse.urlencode(
            {
                "callback_url": server.redirect_uri,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        url = f"{_OPENROUTER_AUTHORIZE}?{query}"
        pasted = ui.show_auth_url(
            url,
            "Complete sign-in in your browser. If the browser is on another "
            "machine, paste the final redirect URL here.",
            "Complete sign-in in your browser, or paste the authorization "
            "code / redirect URL here:",
            server.done,
        )
        code, _client = _code_from(server, pasted, "", None)
        return _exchange_openrouter(code, verifier)
    finally:
        server.close()


def _login_grok(ui: AccountUI) -> dict:
    status, body = post_form(
        _XAI_DEVICE,
        {"client_id": _XAI_CLIENT, "scope": _XAI_SCOPE, "referrer": "pari"},
    )
    if status != 200:
        raise RuntimeError(_http_error("Grok device authorization", status, body))
    uri = _https_uri(body.get("verification_uri"))
    user_code = _required(body, "user_code")
    device_code = _required(body, "device_code")
    expires = body.get("expires_in")
    if not isinstance(expires, (int, float)) or expires <= 0:
        raise RuntimeError("Invalid Grok OAuth response field: expires_in.")
    interval = body.get("interval")
    wait = float(interval) if isinstance(interval, (int, float)) and interval > 0 else 5
    ui.show_device(uri, user_code)
    deadline = time.monotonic() + float(expires)
    while time.monotonic() < deadline:
        if ui.sleep(wait):
            raise LoginCancelled()
        status, token = post_form(
            _XAI_TOKEN,
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": _XAI_CLIENT,
                "device_code": device_code,
            },
        )
        if status == 200 and isinstance(token.get("access_token"), str):
            return _token_fields(token, previous="")
        error = token.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            slower = token.get("interval")
            wait = float(slower) if isinstance(slower, (int, float)) else wait + 5
            continue
        if error in ("access_denied", "authorization_denied"):
            raise RuntimeError("Grok device authorization was denied.")
        if error == "expired_token":
            raise RuntimeError("Grok device code expired.")
        raise RuntimeError(_http_error("Grok device token", status, token))
    raise RuntimeError("Grok device code expired.")


def _refresh_openai(refresh: str, client_id: str) -> dict:
    if not client_id:
        raise RuntimeError("Sign in to OpenAI again.")
    status, body = post_form(
        _OPENAI_TOKEN,
        {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh,
            "resource": _OPENAI_RESOURCE,
        },
    )
    if status != 200:
        raise RuntimeError(_http_error("OpenAI token refresh", status, body))
    return _openai_fields(body, client_id)


def _refresh_anthropic(refresh: str) -> dict:
    status, body = post_json(
        _ANTHROPIC_TOKEN,
        {
            "grant_type": "refresh_token",
            "client_id": _ANTHROPIC_CLIENT,
            "refresh_token": refresh,
        },
    )
    if status != 200:
        raise RuntimeError(_http_error("Anthropic token refresh", status, body))
    return _anthropic_fields(body)


def _refresh_grok(refresh: str) -> dict:
    status, body = post_form(
        _XAI_TOKEN,
        {
            "grant_type": "refresh_token",
            "client_id": _XAI_CLIENT,
            "refresh_token": refresh,
        },
    )
    if status != 200:
        raise RuntimeError(_http_error("Grok token refresh", status, body))
    return _token_fields(body, previous=refresh)


def _exchange_openai(code: str, verifier: str, client_id: str) -> dict:
    status, body = post_form(
        _OPENAI_TOKEN,
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": _OPENAI_REDIRECT,
            "resource": _OPENAI_RESOURCE,
        },
    )
    if status != 200:
        raise RuntimeError(_http_error("OpenAI token exchange", status, body))
    if not isinstance(body.get("id_token"), str) or not body["id_token"].strip():
        raise RuntimeError("OpenAI OAuth token response did not contain an ID token.")
    return _openai_fields(body, client_id)


def _exchange_anthropic(code: str, verifier: str, redirect: str) -> dict:
    status, body = post_json(
        _ANTHROPIC_TOKEN,
        {
            "grant_type": "authorization_code",
            "client_id": _ANTHROPIC_CLIENT,
            "code": code,
            "state": verifier,
            "redirect_uri": redirect,
            "code_verifier": verifier,
        },
    )
    if status != 200:
        raise RuntimeError(_http_error("Anthropic token exchange", status, body))
    return _anthropic_fields(body)


def _exchange_openrouter(code: str, verifier: str) -> dict:
    status, body = post_json(
        _OPENROUTER_TOKEN,
        {
            "code": code,
            "code_verifier": verifier,
            "code_challenge_method": "S256",
        },
    )
    if status != 200:
        raise RuntimeError(_http_error("OpenRouter token exchange", status, body))
    key = body.get("key")
    if not isinstance(key, str) or not key:
        raise RuntimeError('OpenRouter OAuth response carries no "key".')
    return {"access": key, "refresh": "", "expires": None, "client_id": ""}


def _openai_fields(body: dict, client_id: str) -> dict:
    scope = str(body.get("scope") or "")
    if _DIRECT_SCOPE not in scope.split():
        raise RuntimeError(f"OpenAI OAuth grant did not include {_DIRECT_SCOPE}.")
    fields = _token_fields(body, previous="")
    fields["client_id"] = client_id
    return fields


def _anthropic_fields(body: dict) -> dict:
    access = _required(body, "access_token")
    refresh = _required(body, "refresh_token")
    return {
        "access": access,
        "refresh": refresh,
        "expires": _expires_at(body.get("expires_in"), 5 * 60),
        "client_id": "",
    }


def _token_fields(body: dict, previous: str) -> dict:
    access = _required(body, "access_token")
    refresh = body.get("refresh_token")
    if not isinstance(refresh, str) or not refresh:
        refresh = previous
    if not refresh:
        raise RuntimeError("OAuth token response has invalid refresh_token.")
    expires_in = body.get("expires_in")
    if expires_in is None:
        expires_in = 3600
    return {
        "access": access,
        "refresh": refresh,
        "expires": _expires_at(expires_in, 3 * 60),
        "client_id": "",
    }


def _code_from(
    server: "CallbackServer | None",
    pasted: str | None,
    redirect: str,
    state: str | None,
) -> tuple[str, str | None]:
    if server and server.error:
        raise RuntimeError(server.error)
    if server and server.code:
        return server.code, server.client_id
    if not pasted:
        raise LoginCancelled()
    return _parse_paste(pasted, redirect, state)


def _parse_paste(
    text: str, redirect: str, expected_state: str | None
) -> tuple[str, str | None]:
    raw = text.strip()
    if not raw:
        raise ValueError("Paste the full callback URL from the browser.")
    if "://" not in raw and "#" in raw and "=" not in raw.split("#", 1)[0]:
        code, state = raw.split("#", 1)
        if expected_state and state and state != expected_state:
            raise ValueError("OAuth state mismatch.")
        if not code:
            raise ValueError("Missing authorization code.")
        return code, None
    if "://" in raw:
        url = urllib.parse.urlparse(raw)
        if redirect:
            expected = urllib.parse.urlparse(redirect)
            if (url.scheme, url.netloc, url.path) != (
                expected.scheme,
                expected.netloc,
                expected.path,
            ):
                raise ValueError(f"The pasted callback URL must start with {redirect}.")
        query = urllib.parse.parse_qs(url.query)
    elif "=" in raw:
        query = urllib.parse.parse_qs(raw)
    else:
        return raw, None
    error = _first(query, "error")
    if error:
        raise ValueError(f"Authorization failed: {error}.")
    state = _first(query, "state")
    if expected_state and state != expected_state:
        raise ValueError("OAuth state mismatch.")
    code = _first(query, "code")
    if not code:
        raise ValueError("Missing authorization code.")
    return code, _first(query, "client_id")


def _anthropic_url(challenge: str, state: str, redirect: str) -> str:
    query = urllib.parse.urlencode(
        {
            "code": "true",
            "client_id": _ANTHROPIC_CLIENT,
            "response_type": "code",
            "redirect_uri": redirect,
            "scope": _ANTHROPIC_SCOPES,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    return f"{_ANTHROPIC_AUTHORIZE}?{query}"


def _anthropic_server(state: str) -> "CallbackServer | None":
    try:
        return _listen("127.0.0.1", 53692, "/callback", "localhost", state, "Anthropic")
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE:
            return None
    try:
        return _listen("127.0.0.1", 0, "/callback", "localhost", state, "Anthropic")
    except OSError:
        return None


def _callback_path() -> str:
    return "/callback"


class CallbackServer:
    """Loopback redirect. OpenAI's port stays 1455 because the redirect is fixed."""

    def __init__(
        self,
        host: str,
        port: int,
        path: str,
        redirect_uri: str,
        state: str,
        provider: str,
        require_client: bool = False,
    ):
        self.host = host
        self.port = port
        self.path = path
        self.redirect_uri = redirect_uri
        self.state = state
        self.provider = provider
        self.require_client = require_client
        self.done = threading.Event()
        self.code: str | None = None
        self.client_id: str | None = None
        self.error: str | None = None
        self._httpd: ThreadingHTTPServer | None = None

    def start(self) -> None:
        holder = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                holder._handle(self)

            def log_message(self, *_args: object) -> None:
                return

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        bound = self._httpd.server_address[1]
        self.port = bound
        thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        thread.start()

    def close(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def _handle(self, request: BaseHTTPRequestHandler) -> None:
        url = urllib.parse.urlparse(request.path)
        if url.path != self.path:
            _send(request, 404, "Callback route not found.")
            return
        query = urllib.parse.parse_qs(url.query)
        if self.state and _first(query, "state") != self.state:
            _send(request, 400, "State mismatch.")
            return
        error = _first(query, "error")
        if error:
            self.error = f"{self.provider} authorization failed: {error}"
            self.done.set()
            _send(request, 400, self.error)
            return
        code = _first(query, "code")
        if not code:
            _send(request, 400, "Missing authorization code.")
            return
        client_id = _first(query, "client_id")
        if self.require_client and not client_id:
            _send(request, 400, "Missing client id.")
            return
        self.code = code
        self.client_id = client_id
        self.done.set()
        _send(request, 200, f"Signed in to {self.provider}. You can close this window.")


def _listen(
    host: str,
    port: int,
    path: str,
    redirect_host: str,
    state: str,
    provider: str,
    require_client: bool = False,
) -> CallbackServer:
    server = CallbackServer(host, port, path, "", state, provider, require_client)
    server.start()
    server.redirect_uri = f"http://{redirect_host}:{server.port}{path}"
    return server


def _send(request: BaseHTTPRequestHandler, status: int, message: str) -> None:
    body = (
        f"<!doctype html><meta charset=utf-8><title>PARI</title><p>{_html(message)}</p>"
    ).encode()
    request.send_response(status)
    request.send_header("Content-Type", "text/html; charset=utf-8")
    request.send_header("Cache-Control", "no-store")
    request.send_header("Content-Length", str(len(body)))
    request.end_headers()
    request.wfile.write(body)


def post_form(url: str, fields: dict[str, str]) -> tuple[int, dict]:
    return _request(
        url,
        urllib.parse.urlencode(fields).encode(),
        "application/x-www-form-urlencoded",
    )


def post_json(url: str, payload: dict) -> tuple[int, dict]:
    return _request(url, json.dumps(payload).encode(), "application/json")


def _request(url: str, data: bytes, content_type: str) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, _json_body(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _json_body(exc.read())


def _json_body(raw: bytes) -> dict:
    try:
        parsed = json.loads(raw.decode() or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("OAuth token response was not JSON.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("OAuth token response was not a JSON object.")
    return parsed


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def _device_id(store: AuthStore) -> str:
    data = store.load()
    current = data.get("_device")
    if isinstance(current, str) and _uuid_ok(current):
        return current
    current = str(uuid.uuid4())
    data["_device"] = current
    store.save(data)
    return current


def _uuid_ok(value: str) -> bool:
    return re.fullmatch(_UUID, value) is not None


def _expires_at(seconds: object, margin: int) -> int:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise RuntimeError("OAuth token response has invalid expires_in.")
    if seconds <= 0:
        raise RuntimeError("OAuth token response has invalid expires_in.")
    return int(time.time() * 1000 + seconds * 1000 - margin * 1000)


def _required(body: dict, field: str) -> str:
    value = body.get(field)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"OAuth token response has invalid {field}.")
    return value


def _https_uri(value: object) -> str:
    if not isinstance(value, str):
        raise RuntimeError("Untrusted verification URI in Grok OAuth response.")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("Untrusted verification URI in Grok OAuth response.")
    return value


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key) or []
    if not values or not values[0]:
        return None
    return values[0]


def _http_error(action: str, status: int, body: dict) -> str:
    detail = body.get("error_description") or body.get("error") or body.get("message")
    if isinstance(detail, dict):
        detail = detail.get("message")
    suffix = f": {detail}" if isinstance(detail, str) and detail else ""
    return f"{action} failed (HTTP {status}){suffix}."


def _html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
