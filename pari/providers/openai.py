"""PARI Providers: OpenAI Adapter.

Supports GPT-4o, o3-mini, and GPT-4.5 with function calling.
"""

from typing import Any

from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage


class OpenAIProvider(LLMProvider):
    """Adapter for OpenAI Chat Completions API."""

    def __init__(self, model_name: str = "gpt-4o", api_key: str | None = None):
        super().__init__(model_name, api_key)

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Call OpenAI Chat Completions API."""
        raise NotImplementedError
