"""PARI Providers: DeepSeek Adapter.

Supports DeepSeek V3 and DeepSeek R1 via OpenAI-compatible API endpoint.
High performance, cost-effective editor tier model ($0.27/M input, $1.10/M output).
"""

from typing import Any

from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage


class DeepSeekProvider(LLMProvider):
    """Adapter for DeepSeek API using OpenAI-compatible interface."""

    def __init__(self, model_name: str = "deepseek-chat", api_key: str | None = None):
        super().__init__(model_name, api_key)

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Call DeepSeek chat API."""
        raise NotImplementedError
