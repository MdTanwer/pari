"""PARI Providers: Offline / Mock Provider for local testing and dry-runs.

Enables offline testing of the agent loop, tool execution, session recovery,
and diff review without requiring remote cloud API tokens.
"""

from collections.abc import Callable
from typing import Any

from pari.providers.base import LLMProvider
from pari.providers.message import ProviderMessage
from pari.providers.response import ModelResponse


class MockOfflineProvider(LLMProvider):
    """Fallback provider when no cloud API keys are configured."""

    def __init__(self, model_name: str = "mock-offline"):
        super().__init__(model_name, api_key="offline")

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        on_delta: Callable[[str], None] | None = None,
    ) -> ModelResponse:
        """Simulate completion for local testing."""
        _ = tools, temperature
        last_prompt = messages[-1].content if messages else ""
        lower_prompt = last_prompt.lower()

        # If user asks to find python files, simulate a tool call or answer
        if "find" in lower_prompt or "python" in lower_prompt:
            text = "PARI Agent: Found python files in workspace."
            tokens_in, tokens_out = 120, 40
        else:
            text = f"PARI Agent response to: {last_prompt}"
            tokens_in, tokens_out = 80, 30
        if on_delta is not None and text:
            on_delta(text)
        return ModelResponse(
            text=text,
            tool_calls=[],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cached_tokens=0,
            stop_reason="end_turn",
        )
