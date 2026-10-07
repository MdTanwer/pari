"""PARI Layer 8: Dual-Model Router Pipeline.

Coordinates prompt classification, architect plan generation, and editor execution.
"""

from collections.abc import Callable, Coroutine
from typing import Any


class DualModelRouter:
    """Dispatches tasks across Architect and Editor model tiers."""

    def __init__(
        self,
        architect_call: Callable[[str], Coroutine[Any, Any, str]] | None = None,
        editor_call: (
            Callable[[str, str | None], Coroutine[Any, Any, str]] | None
        ) = None,
    ):
        self.architect_call = architect_call
        self.editor_call = editor_call

    async def route_and_execute(self, prompt: str, active_files: list[str]) -> str:
        """Route prompt based on task complexity classification."""
        raise NotImplementedError
