"""Failures from a model API, without the raw response body."""

import asyncio
import json
import random
from typing import Any

import httpx


_DETAIL_LIMIT = 180
_ATTEMPTS = 3
_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


class ProviderError(RuntimeError):
    """The model API refused the call or could not be reached.

    ``detail`` is a short phrase from the provider. The response body stays
    off the message so a traceback cannot dump it into the terminal.
    """

    def __init__(
        self,
        provider: str,
        *,
        status_code: int | None = None,
        code: str = "",
        detail: str = "",
        error_type: str = "",
        kind: str = "http",
    ):
        self.provider = provider
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.error_type = error_type
        self.kind = kind
        super().__init__(detail or _summary(provider, status_code, kind))


def failure_from_body(provider: str, status_code: int, body: str) -> ProviderError:
    """Build a provider error from an HTTP error body."""
    code, detail, error_type = _error_parts(body)
    return ProviderError(
        provider,
        status_code=status_code,
        code=code,
        detail=detail,
        error_type=error_type,
    )


async def checked_post(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    provider: str,
) -> httpx.Response:
    """POST JSON. Retry a dropped read, a connect timeout, 429, or a 5xx."""
    for attempt in range(_ATTEMPTS):
        try:
            response = await client.post(
                url, headers=headers, json=payload, timeout=_TIMEOUT
            )
        except httpx.TimeoutException as exc:
            if attempt + 1 == _ATTEMPTS:
                raise ProviderError(provider, kind="timeout") from exc
            await asyncio.sleep(_backoff(attempt))
            continue
        except httpx.ReadError as exc:
            if attempt + 1 == _ATTEMPTS:
                raise ProviderError(provider, kind="network") from exc
            await asyncio.sleep(_backoff(attempt))
            continue
        except httpx.HTTPError as exc:
            raise ProviderError(provider, kind="network") from exc
        if response.status_code < 400:
            return response
        failure = failure_from_body(provider, response.status_code, response.text)
        if attempt + 1 == _ATTEMPTS or not _retry_status(response.status_code):
            raise failure
        await asyncio.sleep(_backoff(attempt))
    raise ProviderError(provider, kind="network")


def _backoff(attempt: int) -> float:
    """Short wait that grows, plus jitter so retries do not line up."""
    return 0.2 * (2**attempt) + random.uniform(0, 0.2)


def _retry_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def _summary(provider: str, status_code: int | None, kind: str) -> str:
    if kind == "timeout":
        return f"{provider} did not respond in time."
    if kind == "network":
        return f"Could not reach {provider}."
    if status_code is None:
        return f"{provider} request failed."
    return f"{provider} request failed ({status_code})."


def _error_parts(body: str) -> tuple[str, str, str]:
    """Provider code, message, and type. An HTML body contributes none of them."""
    text = body.strip()
    if not text or text.lstrip().startswith("<"):
        return "", "", ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return "", _clip(text), ""
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
