"""POST to a model API with a bounded retry."""

import asyncio
import random
from collections.abc import AsyncIterator
from typing import Any

import httpx

from pari.providers.exceptions import (
    ProviderError,
    failure_from_body,
    is_retryable_status,
)


_ATTEMPTS = 3
_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


async def checked_post(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    provider: str,
) -> httpx.Response:
    """POST JSON. Retry a dropped read, a timeout, 429, or a 5xx."""
    for attempt in range(_ATTEMPTS):
        last = attempt + 1 == _ATTEMPTS
        try:
            response = await client.post(
                url, headers=headers, json=payload, timeout=_TIMEOUT
            )
        except httpx.TimeoutException as exc:
            if last:
                raise ProviderError(provider, kind="timeout") from exc
            await asyncio.sleep(_backoff(attempt))
            continue
        except httpx.ReadError as exc:
            if last:
                raise ProviderError(provider, kind="network") from exc
            await asyncio.sleep(_backoff(attempt))
            continue
        except httpx.HTTPError as exc:
            raise ProviderError(provider, kind="network") from exc
        if response.status_code < 400:
            return response
        failure = failure_from_body(provider, response.status_code, response.text)
        if last or not is_retryable_status(response.status_code):
            raise failure
        await asyncio.sleep(_backoff(attempt))
    raise ProviderError(provider, kind="network")


async def iter_sse(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    provider: str,
) -> AsyncIterator[str]:
    """POST a streaming completion and yield each SSE line."""
    for attempt in range(_ATTEMPTS):
        last = attempt + 1 == _ATTEMPTS
        try:
            async with client.stream(
                "POST", url, headers=headers, json=payload, timeout=_TIMEOUT
            ) as response:
                if response.status_code >= 400:
                    raw = (await response.aread()).decode("utf-8", errors="replace")
                    failure = failure_from_body(provider, response.status_code, raw)
                    if last or not is_retryable_status(response.status_code):
                        raise failure
                    await asyncio.sleep(_backoff(attempt))
                    continue
                async for line in response.aiter_lines():
                    yield line
                return
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            if last:
                raise ProviderError(provider, kind="timeout") from exc
            await asyncio.sleep(_backoff(attempt))
        except httpx.ReadError as exc:
            if last:
                raise ProviderError(provider, kind="network") from exc
            await asyncio.sleep(_backoff(attempt))
        except httpx.HTTPError as exc:
            raise ProviderError(provider, kind="network") from exc
    raise ProviderError(provider, kind="network")


def _backoff(attempt: int) -> float:
    """Short wait that grows, plus jitter so retries do not line up."""
    return 0.2 * (2**attempt) + random.uniform(0, 0.2)
