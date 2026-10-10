"""Sign in, sign out, and find the credential to send.

An API key and an account token are stored the same way and sent as that
provider's credential. There is no Radius login.
"""

import os
import time
from collections.abc import Callable

from pari.auth.credential import parse_sign_in
from pari.auth.providers import PROVIDERS, ProviderInfo, get_info
from pari.auth.store import AuthStore, saved_row


KeyVerifier = Callable[[ProviderInfo, str], None]

NO_MODEL = (
    "No model selected. Sign in with `pari-cli login`, "
    "or pass --model, or set PARI_MODEL."
)


def sign_in(
    provider_id: str,
    secret: str,
    method: str,
    store: AuthStore | None = None,
    extra: dict | None = None,
    verify: KeyVerifier | None = None,
) -> str:
    """Record one provider. method is ``api_key`` or ``account``.

    ``verify`` runs on an API key after the format check and before anything is
    saved. It raises ``ValueError`` to refuse the key.
    """
    request = parse_sign_in(provider_id, secret, method, extra)
    info = request.info
    if verify is not None and request.method == "api_key":
        verify(info, request.secret)
    auth = store or AuthStore()
    data = auth.load()
    # Latest sign-in is the session default, so it has to be last.
    data.pop(info.id, None)
    data[info.id] = request.model_dump(exclude={"provider_id"}, exclude_none=True)
    auth.save(data)
    label = "API key" if request.method == "api_key" else "account"
    return f"Signed in to {info.label} with an {label}."


def sign_out(provider_id: str, store: AuthStore | None = None) -> str:
    info = get_info(provider_id)
    auth = store or AuthStore()
    data = auth.load()
    if data.pop(info.id, None) is None:
        return f"{info.label} is not signed in."
    auth.save(data)
    return f"Signed out of {info.label}."


def status_text(store: AuthStore | None = None) -> str:
    """Who is signed in. The token itself is not included."""
    data = (store or AuthStore()).load()
    lines = ["Sign in with an API key or an account token."]
    for info in PROVIDERS:
        lines.append(f"{info.id}: {_state(saved_row(data, info.id))}")
    return "\n".join(lines)


def resolve_secret(info: ProviderInfo, store: AuthStore | None = None) -> str | None:
    """Environment first, then the saved sign-in.

    An expired account token is refreshed before it is returned. The refresh
    token itself is never returned.
    """
    env = _env_secret(info)
    if env:
        return env
    auth = store or AuthStore()
    row = saved_row(auth.load(), info.id)
    if row is None:
        return None
    if _needs_refresh(row):
        # account.py imports sign_in from this module.
        from pari.auth.account import refresh_saved

        return refresh_saved(info, row, auth)
    return row["secret"].strip()


def default_model_name(store: AuthStore | None = None) -> str | None:
    """Model used when the CLI was started without ``--model``.

    ``PARI_MODEL`` wins. Otherwise the latest saved sign-in is used, then an
    API key already in the environment. Nothing is chosen when no credential
    is available.
    """
    chosen = os.environ.get("PARI_MODEL", "").strip()
    if chosen:
        return chosen
    data = (store or AuthStore()).load()
    for provider_id in reversed(list(data)):
        if saved_row(data, provider_id) is None:
            continue
        try:
            return get_info(provider_id).default_model
        except ValueError:
            continue
    for info in PROVIDERS:
        if _env_secret(info):
            return info.default_model
    return None


def sign_in_hint(info: ProviderInfo) -> str:
    if not info.account:
        return f"Sign in to {info.label}: pari-cli login {info.id} --api-key <key>."
    return (
        f"Sign in to {info.label}: "
        f"pari-cli login {info.id} --api-key <key> "
        f"or pari-cli login {info.id} --account <token>."
    )


def _env_secret(info: ProviderInfo) -> str:
    return os.environ.get(info.env, "").strip()


def _needs_refresh(row: dict) -> bool:
    expires = row.get("expires")
    refresh = row.get("refresh")
    return (
        isinstance(expires, int)
        and expires <= _now_ms()
        and isinstance(refresh, str)
        and bool(refresh.strip())
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


def _state(row: dict | None) -> str:
    if row is None:
        return "not signed in"
    if row.get("method") == "account":
        return "signed in with an account"
    return "signed in with an API key"
