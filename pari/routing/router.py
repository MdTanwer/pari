"""PARI Layer 8: Dual-Model Router Pipeline.

Coordinates prompt classification, architect plan generation, and editor execution.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from pari.providers import get_provider
from pari.providers.base import LLMProvider
from pari.providers.message import ProviderMessage
from pari.providers.response import ModelResponse
from pari.routing.anti_verbosity import enforce_planning_ceiling
from pari.routing.classifier import TaskClassifier, TaskComplexity


# The architect may only plan. Tool calls belong to the editor step.
_PLAN_ONLY = (
    "Write a short natural-language plan. Do not emit code, "
    "search/replace blocks, or tool calls."
)
_PARTIAL = (
    "Execute the completed portion of this plan directly onto disk. "
    "Remainder tasks will be scheduled iteratively."
)
_ARCHITECT_MODEL = "claude-3-7-sonnet-20250219"


class DualModelRouter:
    """Send a wide task through the architect, and a small edit to the editor."""

    def __init__(
        self,
        architect_call: Callable[[str], Coroutine[Any, Any, str]] | None = None,
        editor_call: (
            Callable[[str, str | None], Coroutine[Any, Any, str]] | None
        ) = None,
    ):
        self.architect_call = architect_call
        self.editor_call = editor_call
        self.architect: LLMProvider | None = None
        self.editor: LLMProvider | None = None
        self.plan: str | None = None
        self.last_route = TaskComplexity.SIMPLE_EDIT

    @classmethod
    def from_providers(
        cls, architect: LLMProvider, editor: LLMProvider
    ) -> "DualModelRouter":
        """Bind the two models the turn loop will call."""
        router = cls()
        router.architect = architect
        router.editor = editor
        return router

    def begin_turn(self) -> None:
        """A new user prompt may need a new plan. Tool steps reuse this one."""
        self.plan = None

    async def route_and_execute(self, prompt: str, active_files: list[str]) -> str:
        """Classify, optionally plan, then ask the editor to apply the result."""
        plan: str | None = None
        if _is_wide(prompt, active_files):
            if self.architect_call is None:
                raise RuntimeError("No architect model is configured.")
            plan = _bounded_plan(await self.architect_call(prompt))
        if self.editor_call is None:
            raise RuntimeError("No editor model is configured.")
        return await self.editor_call(prompt, plan)

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None,
        *,
        prompt: str,
        active_files: list[str],
        on_delta: Callable[[str], None] | None = None,
    ) -> ModelResponse:
        """One loop step. A wide task plans once, then the editor may use tools."""
        if self.editor is None:
            raise RuntimeError("No editor model is configured.")
        wide = _is_wide(prompt, active_files)
        self.last_route = (
            TaskComplexity.ARCHITECTURAL if wide else TaskComplexity.SIMPLE_EDIT
        )
        planned_tokens = (0, 0, 0)
        editor_messages = messages
        if wide and self.plan is None:
            if self.architect is None:
                raise RuntimeError("No architect model is configured.")
            planned = await self.architect.complete(
                [ProviderMessage(role="system", content=_PLAN_ONLY), *messages],
                tools=None,
            )
            self.plan = _bounded_plan(planned.text)
            planned_tokens = (
                planned.tokens_in,
                planned.tokens_out,
                planned.cached_tokens,
            )
            editor_messages = [
                *messages,
                ProviderMessage(role="user", content=f"Plan:\n{self.plan}"),
            ]
        if on_delta is None:
            edited = await self.editor.complete(editor_messages, tools=tools)
        else:
            edited = await self.editor.complete(
                editor_messages, tools=tools, on_delta=on_delta
            )
        if planned_tokens == (0, 0, 0):
            return edited
        return ModelResponse(
            text=edited.text,
            tool_calls=list(edited.tool_calls),
            tokens_in=edited.tokens_in + planned_tokens[0],
            tokens_out=edited.tokens_out + planned_tokens[1],
            cached_tokens=edited.cached_tokens + planned_tokens[2],
            stop_reason=edited.stop_reason,
        )


def router_for(editor: LLMProvider) -> DualModelRouter:
    """Pair a Haiku editor with Sonnet. Any other editor plans with itself."""
    architect = editor
    if "haiku" in editor.model_name:
        try:
            architect = get_provider(_ARCHITECT_MODEL)
        except (RuntimeError, NotImplementedError):
            architect = editor
    return DualModelRouter.from_providers(architect, editor)


def _is_wide(prompt: str, active_files: list[str]) -> bool:
    return TaskClassifier.classify(prompt, active_files) == TaskComplexity.ARCHITECTURAL


def _bounded_plan(plan_text: str) -> str:
    plan = enforce_planning_ceiling(plan_text)
    if "ANTI-VERBOSITY GUARD" in plan:
        return f"{plan}\n{_PARTIAL}"
    return plan
