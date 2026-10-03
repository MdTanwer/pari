"""PARI Layer 8: Dual-Model Router Pipeline.

Coordinates prompt classification, architect plan generation, and editor execution.
"""

from typing import Any, Callable, Coroutine, List, Optional
from pari.routing.classifier import TaskClassifier, TaskComplexity


class DualModelRouter:
    """Dispatches tasks across Architect and Editor model tiers."""

    def __init__(
        self,
        architect_call: Optional[Callable[[str], Coroutine[Any, Any, str]]] = None,
        editor_call: Optional[Callable[[str, Optional[str]], Coroutine[Any, Any, str]]] = None,
    ):
        self.architect_call = architect_call
        self.editor_call = editor_call

    async def route_and_execute(self, prompt: str, active_files: List[str]) -> str:
        """Route prompt based on task complexity classification."""
        raise NotImplementedError
