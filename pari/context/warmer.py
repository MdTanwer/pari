"""PARI Layer 2: Autonomous Economic Cache Warmer.

Architectural Purpose:
    Harvested from Pi's cache-warmer.ts.
    Cloud LLM prompt caches (Anthropic KV cache) expire after 5 minutes of inactivity.
    If the developer pauses for 6 minutes while reading or typing, the next turn suffers
    a full 100% cache-miss billing spike.
    The CacheWarmer sends a lightweight keep-alive request every 4.5 minutes to maintain
    cache warm status at negligible cost (<$0.001/hr).
"""

import asyncio
import inspect
import time
from collections.abc import Callable


# 90% of the 300s Anthropic cache TTL. A ping at 270s refreshes the prefix.
DEFAULT_INTERVAL_SECONDS = 270.0
# Chance an idle developer sends another turn inside the next TTL window.
P_CONTINUATION = 0.15
# Cache-write price and cache-read price, dollars per million input tokens.
MISS_PER_MILLION = 3.75
WARM_PER_MILLION = 0.375
# One output token on the ping, at the architect output price.
PING_OUTPUT_PER_MILLION = 15.0
MIN_SAVINGS_USD = 0.05


def expected_savings(context_tokens: int) -> float:
    """E[savings] = (P_continuation * miss cost) - warm cost.

    Change the prices above if the provider price changes. The $0.05 floor
    is the point where a ping is worth sending.
    """
    tokens = max(0, context_tokens)
    miss = tokens * MISS_PER_MILLION / 1_000_000
    warm = tokens * WARM_PER_MILLION / 1_000_000 + PING_OUTPUT_PER_MILLION / 1_000_000
    return (P_CONTINUATION * miss) - warm


def should_warm(context_tokens: int) -> bool:
    """True when a 1-token ping is expected to save at least $0.05."""
    return expected_savings(context_tokens) >= MIN_SAVINGS_USD


class CacheWarmer:
    """Wait out the idle window, then ping only when the savings clear $0.05."""

    def __init__(
        self,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        warm_callback: Callable | None = None,
        context_tokens: int = 0,
    ):
        self.interval_seconds = interval_seconds
        self.warm_callback = warm_callback
        self.context_tokens = context_tokens
        self._touched = 0.0
        self._task: asyncio.Task[None] | None = None

    def touch(self) -> None:
        """The developer typed. The idle window starts over."""
        self._touched = time.monotonic()

    def start(self) -> None:
        """Start the background wait. Calling start again leaves the running task."""
        if self._task is not None and not self._task.done():
            return
        self.touch()
        self._task = asyncio.get_running_loop().create_task(self._loop())

    async def stop(self) -> None:
        """Cancel the background wait."""
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _loop(self) -> None:
        while True:
            started = time.monotonic()
            await asyncio.sleep(self.interval_seconds)
            # A keystroke during the wait means the next real turn will refresh.
            if self._touched > started:
                continue
            if not should_warm(self.context_tokens) or self.warm_callback is None:
                continue
            result = self.warm_callback()
            if inspect.isawaitable(result):
                await result
