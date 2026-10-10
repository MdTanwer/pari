"""PARI Providers: Base LLM Interface.

Defines the contract for calling LLM inference APIs with tool calling and prompt
caching.
"""

from abc import ABC, abstractmethod
from typing import Any

from pari.providers.message import ProviderMessage
from pari.providers.response import ModelResponse


class LLMProvider(ABC):
    """Abstract base class for all LLM backend adapters."""

    def __init__(self, model_name: str, api_key: str | None = None):
        self.model_name = model_name
        self.api_key = api_key

    @abstractmethod
    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Execute a completion request."""
        raise NotImplementedError
