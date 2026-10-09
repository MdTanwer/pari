"""Sign in with an API key or an account token.

Both are stored the same way and sent as that provider's credential. There is
no Radius login.
"""

import os
import re
import time

from pari.auth.providers import PROVIDERS, ProviderInfo, get_info
from pari.auth.store import AuthStore


# A pasted sentence or another provider's key must not be stored as a success.
_API_KEY_PREFIX = {
    "openai": "sk-",
    "deepseek": "sk-",
    "anthropic": "sk-ant-",
    "grok": "xai-",
    "openrouter": "sk-or-",
}
_KEY_CHARS = re.compile(r"^[A-Za-z0-9_-]+$")
_MIN_API_KEY = 20


def sign_in(
    provider_id: str,
    secret: str,
    method: str,
    store: AuthStore | None = None,
    extra: dict | None = None,
) -> str:
    """Record one provider. method is ``api_key`` or ``account``."""
    if method not in ("api_key", "account"):
        raise ValueError("Sign in with an API key or an account token.")
    info = get_info(provider_id)
    if method == "account" and info.id == "deepseek":
        raise ValueError(
            "DeepSeek has no account sign-in. "
            "Use pari-cli login deepseek --api-key <key>."
        )
    token = secret.strip()
    if not token:
        raise ValueError("The credential is empty.")
    if method == "api_key":
        _check_api_key(info, token)
    auth = store or AuthStore()
    data = auth.load()
    row: dict = {"method": method, "secret": token}
    for key in ("refresh", "client_id"):
        value = (extra or {}).get(key)
        if isinstance(value, str) and value.strip():
            row[key] = value.strip()
    expires = (extra or {}).get("expires")
    if isinstance(expires, int):
        row["expires"] = expires
    data[info.id] = row
    auth.save(data)
    label = "API key" if method == "api_key" else "account"
    return f"Signed in to {info.label} with an {label}."


def _check_api_key(info: ProviderInfo, token: str) -> None:
    prefix = _API_KEY_PREFIX[info.id]
    if any(char.isspace() for char in token):
        raise ValueError(f"{info.label} API keys cannot contain spaces.")
    found = _key_family(token)
    expected = _key_family(prefix + ("a" * _MIN_API_KEY))
    if found and found != expected:
        raise ValueError(
            f"That key belongs to {found}. {info.label} keys start with {prefix}."
        )
    if not token.startswith(prefix):
        raise ValueError(f"{info.label} API keys start with {prefix}.")
    if not _KEY_CHARS.fullmatch(token):
        raise ValueError(
            f"That {info.label} API key uses characters that are not allowed."
        )
    if len(token) < _MIN_API_KEY:
        raise ValueError(f"That {info.label} API key is too short.")


def _key_family(token: str) -> str:
    if token.startswith("sk-ant-"):
        return "Anthropic"
    if token.startswith("sk-or-"):
        return "OpenRouter"
    if token.startswith("xai-"):
        return "Grok"
    if token.startswith("sk-"):
        return "OpenAI or DeepSeek"
    return ""


def sign_out(provider_id: str, store: AuthStore | None = None) -> str:
    info = get_info(provider_id)
    auth = store or AuthStore()
    data = auth.load()
    if info.id not in data:
        return f"{info.label} is not signed in."
    del data[info.id]
    auth.save(data)
    return f"Signed out of {info.label}."


def status_text(store: AuthStore | None = None) -> str:
    """Who is signed in. The token itself is not included."""
    data = (store or AuthStore()).load()
    lines = ["Sign in with an API key or an account token."]
    for info in PROVIDERS:
        lines.append(f"{info.id}: {_state(data.get(info.id))}")
    return "\n".join(lines)


def resolve_secret(info: ProviderInfo, store: AuthStore | None = None) -> str | None:
    """Environment first, then the saved sign-in.

    An expired account token is refreshed before it is returned. The refresh
    token itself is never returned.
    """
    env = os.environ.get(info.env, "").strip()
    if env:
        return env
    auth = store or AuthStore()
    row = auth.load().get(info.id)
    if not isinstance(row, dict):
        return None
    secret = row.get("secret")
    if not isinstance(secret, str) or not secret.strip():
        return None
    expires = row.get("expires")
    refresh = row.get("refresh")
    if (
        isinstance(expires, int)
        and expires <= _now_ms()
        and isinstance(refresh, str)
        and refresh.strip()
    ):
        from pari.auth.account import refresh_saved

        return refresh_saved(info, row, auth)
    return secret.strip()


def _now_ms() -> int:
    return int(time.time() * 1000)


def sign_in_hint(info: ProviderInfo) -> str:
    if info.id == "deepseek":
        return "Sign in to DeepSeek: pari-cli login deepseek --api-key <key>."
    return (
        f"Sign in to {info.label}: "
        f"pari-cli login {info.id} --api-key <key> "
        f"or pari-cli login {info.id} --account <token>."
    )


def _state(row: object) -> str:
    if not isinstance(row, dict) or not str(row.get("secret") or "").strip():
        return "not signed in"
    if row.get("method") == "account":
        return "signed in with an account"
    return "signed in with an API key"
