"""PARI Layer 8: Dual-Model Router Pipeline.

Coordinates prompt classification, architect plan generation, and editor execution.
"""

from typing import Any, Callable, Coroutine, List, Optional
from pari.routing.classifier import TaskClassifier, TaskComplexity
from pari.routing.anti_verbosity import enforce_planning_ceiling


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
        complexity = TaskClassifier.classify(prompt, active_files)

        if complexity == TaskComplexity.SIMPLE_EDIT or not self.architect_call:
            # Bypass architect
            if self.editor_call:
                return await self.editor_call(prompt, None)
            return "No editor provider registered."

        # Step 1: Architect planning
        raw_plan = await self.architect_call(prompt)
        plan = enforce_planning_ceiling(raw_plan)

        # Step 2: Editor diff execution
        if self.editor_call:
            return await self.editor_call(prompt, plan)

        return plan
