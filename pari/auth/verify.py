"""Ask the provider whether an API key is accepted, before it is saved.

The format check in ``credential.py`` catches typos. It cannot tell a revoked or
made-up key from a real one, so one authenticated read-only request does.
"""

import httpx

from pari.auth.providers import ProviderInfo


_TIMEOUT_SECONDS = 10.0
_ANTHROPIC_VERSION = "2023-06-01"
# Read-only endpoints that need a valid key. OpenRouter's /models is public,
# so its key endpoint is used instead.
_CHECK_URL = {
    "openai": "https://api.openai.com/v1/models",
    "deepseek": "https://api.deepseek.com/models",
    "anthropic": "https://api.anthropic.com/v1/models",
    "grok": "https://api.x.ai/v1/models",
    "openrouter": "https://openrouter.ai/api/v1/auth/key",
}


def verify_api_key(
    info: ProviderInfo,
    key: str,
    transport: httpx.BaseTransport | None = None,
) -> None:
    """Return when the provider accepts the key. Raise ``ValueError`` otherwise.

    A key that cannot be checked is refused too. The message never contains the
    key.
    """
    try:
        with httpx.Client(transport=transport, timeout=_TIMEOUT_SECONDS) as client:
            response = client.get(_CHECK_URL[info.id], headers=_headers(info, key))
    except httpx.HTTPError:
        raise ValueError(
            f"Could not reach {info.label} to check the key. "
            "Check your connection and try again."
        ) from None
    if response.status_code in (401, 403):
        raise ValueError(f"{info.label} rejected that API key. Check it and try again.")
    if not response.is_success:
        raise ValueError(
            f"{info.label} could not check the key (HTTP {response.status_code}). "
            "Try again later."
        )


def _headers(info: ProviderInfo, key: str) -> dict[str, str]:
    if info.id == "anthropic":
        return {"x-api-key": key, "anthropic-version": _ANTHROPIC_VERSION}
    return {"Authorization": f"Bearer {key}"}
