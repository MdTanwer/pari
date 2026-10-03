"""PARI Multi-Provider LLM Integration Layer.

Architectural Purpose:
    Closes Antigravity F5 (Hard Google API lock-in) and Claude Code Anthropic exclusivity.
    Provides unified model abstraction across Anthropic Claude, OpenAI, DeepSeek, local Ollama,
    and an offline fallback provider for local testing.
"""

from typing import Optional
from pari.providers.base import LLMProvider, ProviderMessage, ModelResponse, ToolCall


def get_provider(model_name: Optional[str] = None) -> LLMProvider:
    """Instantiate the best available LLM provider based on model name and environment."""
    raise NotImplementedError


__all__ = [
    "LLMProvider",
    "ProviderMessage",
    "ModelResponse",
    "ToolCall",
    "get_provider",
]
