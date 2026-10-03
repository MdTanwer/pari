"""PARI Providers: Anthropic Claude Adapter.

Supports Claude 3.7 Sonnet, Claude 3.5 Sonnet, and Claude 3.5 Haiku with prompt caching.
"""

from typing import Any, Dict, List, Optional
from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage


class AnthropicProvider(LLMProvider):
    """Adapter for Anthropic Messages API."""

    def __init__(self, model_name: str = "claude-3-7-sonnet-20250219", api_key: Optional[str] = None):
        super().__init__(model_name, api_key)

    async def complete(
        self,
        messages: List[ProviderMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Call Anthropic Messages API with prompt caching."""
        raise NotImplementedError
