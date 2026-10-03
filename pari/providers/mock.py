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
        raise NotImplementedError
