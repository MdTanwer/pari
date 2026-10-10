"""PARI Providers: Local Ollama Adapter.

Supports local models (Llama 3, Qwen 2.5 Coder, DeepSeek R1 distilled) via local HTTP
endpoint.
Allows 100% offline, private coding agent execution without external cloud tokens.
"""

from typing import Any

from pari.providers.base import LLMProvider
from pari.providers.message import ProviderMessage
from pari.providers.response import ModelResponse


class OllamaProvider(LLMProvider):
    """Adapter for locally hosted Ollama instances."""

    def __init__(
        self,
        model_name: str = "qwen2.5-coder:7b",
        base_url: str = "http://localhost:11434/v1",
    ):
        super().__init__(model_name, api_key="ollama")
        self.base_url = base_url

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Call local Ollama endpoint."""
        raise NotImplementedError
