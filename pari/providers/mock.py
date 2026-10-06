"""PARI Providers: Offline / Mock Provider for local testing and dry-runs.

Enables offline testing of the agent loop, tool execution, session recovery,
and diff review without requiring remote cloud API tokens.
"""

from typing import Any, Dict, List, Optional
from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage


class MockOfflineProvider(LLMProvider):
    """Fallback provider when no cloud API keys are configured."""

    def __init__(self, model_name: str = "mock-offline"):
        super().__init__(model_name, api_key="offline")

    async def complete(
        self,
        messages: List[ProviderMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Simulate completion for local testing."""
        last_prompt = messages[-1].content if messages else ""
        lower_prompt = last_prompt.lower()

        # If user asks to find python files, simulate a tool call or answer
        if "find" in lower_prompt or "python" in lower_prompt:
            return ModelResponse(
                text="PARI Agent: Found python files in workspace.",
                tool_calls=[],
                tokens_in=120,
                tokens_out=40,
                cached_tokens=0,
                stop_reason="end_turn",
            )

        return ModelResponse(
            text=f"PARI Agent response to: {last_prompt}",
            tool_calls=[],
            tokens_in=80,
            tokens_out=30,
            cached_tokens=0,
            stop_reason="end_turn",
        )

