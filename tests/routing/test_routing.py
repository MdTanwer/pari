"""Unit tests for Layer 8 Dual-Model Routing & Anti-Verbosity Guard."""

import pytest

from pari.agent.runtime import AgentRuntime
from pari.providers.anthropic import AnthropicProvider
from pari.providers.base import LLMProvider
from pari.providers.message import ProviderMessage
from pari.providers.response import ModelResponse
from pari.routing.anti_verbosity import enforce_planning_ceiling
from pari.routing.classifier import TaskClassifier, TaskComplexity
from pari.routing.router import DualModelRouter, router_for


def test_task_classifier():
    c1 = TaskClassifier.classify("Fix typo in README", ["README.md"])
    assert c1 == TaskComplexity.SIMPLE_EDIT

    files = ["a.py", "b.py", "c.py", "d.py"]
    c2 = TaskClassifier.classify("Redesign system architecture", files)
    assert c2 == TaskComplexity.ARCHITECTURAL


def test_anti_verbosity_ceiling():
    small_plan = "Step 1: Edit file\nStep 2: Run tests"
    assert enforce_planning_ceiling(small_plan, max_tokens=100) == small_plan

    large_plan = "plan line\n" * 1000
    capped = enforce_planning_ceiling(large_plan, max_tokens=50)
    assert "[PARI ANTI-VERBOSITY GUARD" in capped


@pytest.mark.asyncio
async def test_simple_edit_skips_the_architect():
    seen: list[str | None] = []

    async def architect(_prompt: str) -> str:
        seen.append("architect")
        return "plan"

    async def editor(_prompt: str, plan: str | None) -> str:
        seen.append(plan)
        return "edited"

    router = DualModelRouter(architect, editor)
    text = await router.route_and_execute("Fix typo in README", ["README.md"])
    assert text == "edited"
    assert seen == [None]


@pytest.mark.asyncio
async def test_wide_task_sends_the_plan_to_the_editor():
    async def architect(_prompt: str) -> str:
        return "move the auth check"

    async def editor(_prompt: str, plan: str | None) -> str:
        return plan or ""

    router = DualModelRouter(architect, editor)
    files = ["a.py", "b.py", "c.py"]
    text = await router.route_and_execute("Redesign system architecture", files)
    assert text == "move the auth check"


class _RecordingProvider(LLMProvider):
    def __init__(self, name: str, text: str):
        super().__init__(name)
        self.text = text
        self.saw_tools: list[bool] = []
        self.last_user = ""

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        _ = temperature
        self.saw_tools.append(tools is not None)
        for message in reversed(messages):
            if message.role == "user":
                self.last_user = message.content
                break
        return ModelResponse(text=self.text, tokens_in=3, tokens_out=2)


@pytest.mark.asyncio
async def test_turn_skips_the_architect_for_a_typo(tmp_path):
    architect = _RecordingProvider("architect", "plan")
    editor = _RecordingProvider("editor", "done")
    runtime = AgentRuntime(
        tmp_path,
        provider=editor,
        router=DualModelRouter.from_providers(architect, editor),
    )
    text = await runtime.execute_turn("Fix the typo in the readme")
    assert text == "done"
    assert architect.saw_tools == []
    assert editor.saw_tools == [True]


@pytest.mark.asyncio
async def test_turn_plans_once_then_edits(tmp_path):
    architect = _RecordingProvider("architect", "move the auth check")
    editor = _RecordingProvider("editor", "applied")
    runtime = AgentRuntime(
        tmp_path,
        provider=editor,
        router=DualModelRouter.from_providers(architect, editor),
    )
    text = await runtime.execute_turn("Redesign system architecture")
    assert text == "applied"
    assert architect.saw_tools == [False]
    assert editor.saw_tools == [True]
    assert "move the auth check" in editor.last_user
    assert runtime.router.last_route == TaskComplexity.ARCHITECTURAL


def test_haiku_editor_pairs_with_sonnet(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    editor = AnthropicProvider("claude-3-5-haiku-20241022", "test-key")
    router = router_for(editor)
    assert router.architect is not None
    assert router.architect.model_name == "claude-3-7-sonnet-20250219"
    assert router.editor is editor
