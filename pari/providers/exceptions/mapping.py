"""Map an HTTP body to a ProviderError without keeping the raw body."""

import json

import httpx

from pari.providers.exceptions.types import ProviderError


_DETAIL_LIMIT = 180


def decode_body(response: httpx.Response, provider: str) -> object:
    """Parse a success body. A non-JSON page stays off the error text."""
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError(
            provider, detail="The model response was not JSON."
        ) from exc


def failure_from_body(provider: str, status_code: int, body: str) -> ProviderError:
    """Build a provider error from an HTTP error body."""
    text = body.strip()
    if not text or text.startswith("<"):
        return ProviderError(provider, status_code=status_code)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return ProviderError(provider, status_code=status_code, detail=_clip(text))
    return failure_from_payload(provider, payload, status_code=status_code)


def failure_from_payload(
    provider: str,
    payload: object,
    *,
    status_code: int | None = None,
    default_detail: str = "",
) -> ProviderError:
    """Build a provider error from a parsed body.

    Some providers answer 200 with an ``error`` object instead of a result.
    """
    code, detail, error_type = _error_parts(payload)
    return ProviderError(
        provider,
        status_code=status_code,
        code=code,
        detail=detail or default_detail,
        error_type=error_type,
    )


def _error_parts(payload: object) -> tuple[str, str, str]:
    """Provider code, message, and type from a parsed body."""
    if not isinstance(payload, dict):
        return "", "", ""
    error = payload.get("error")
    if isinstance(error, str):
        return "", _clip(error), ""
    if isinstance(error, dict):
        return (
            _code(error.get("code")),
            _clip(_text(error.get("message"))),
            _code(error.get("type")),
        )
    return _code(payload.get("code")), _clip(_text(payload.get("message"))), ""


def _code(value: object) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _text(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


def _clip(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= _DETAIL_LIMIT:
        return flat
    return flat[: _DETAIL_LIMIT - 3] + "..."
