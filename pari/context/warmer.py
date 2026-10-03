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
import time
from typing import Callable, Optional


class CacheWarmer:
    """Maintains prompt cache warmth via periodic lightweight async pings."""

    def __init__(self, interval_seconds: float = 270.0, warm_callback: Optional[Callable] = None):
        self.interval_seconds = interval_seconds
        self.warm_callback = warm_callback
        self._task: Optional[asyncio.Task] = None
        self._last_activity = time.time()
        self._running = False

    def touch(self):
        """Mark recent interaction to reset idle timer."""
        self._last_activity = time.time()

    async def _loop(self):
        while self._running:
            await asyncio.sleep(30.0)
            elapsed = time.time() - self._last_activity
            if elapsed >= self.interval_seconds:
                if self.warm_callback:
                    try:
                        await self.warm_callback()
                    except Exception:
                        pass
                self._last_activity = time.time()

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
