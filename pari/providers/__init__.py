"""PARI Multi-Provider LLM Integration Layer.

Architectural Purpose:
    Closes Antigravity F5 (Hard Google API lock-in) and Claude Code Anthropic exclusivity.
    Provides unified model abstraction across Anthropic Claude, OpenAI, DeepSeek, local Ollama,
    and an offline fallback provider for local testing.
"""

import os
from typing import Optional

from pari.providers.base import LLMProvider, ProviderMessage, ModelResponse, ToolCall
from pari.providers.anthropic import AnthropicProvider
from pari.providers.openai import OpenAIProvider
from pari.providers.deepseek import DeepSeekProvider
from pari.providers.ollama import OllamaProvider
from pari.providers.mock import MockOfflineProvider


def get_provider(model_name: Optional[str] = None) -> LLMProvider:
    """Instantiate the best available LLM provider based on model name and environment."""
    model = (model_name or os.environ.get("PARI_MODEL", "claude-3-7-sonnet")).lower()

    if "claude" in model:
        if os.environ.get("ANTHROPIC_API_KEY"):
            return AnthropicProvider(model_name=model)
    elif "gpt" in model or "o3" in model or "o1" in model:
        if os.environ.get("OPENAI_API_KEY"):
            return OpenAIProvider(model_name=model)
    elif "deepseek" in model:
        if os.environ.get("DEEPSEEK_API_KEY"):
            return DeepSeekProvider(model_name=model)
    elif "ollama" in model:
        return OllamaProvider(model_name=model)

    # Automatic selection based on whichever key is present in environment
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicProvider()
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIProvider()
    if os.environ.get("DEEPSEEK_API_KEY"):
        return DeepSeekProvider()

    # Graceful fallback to MockOfflineProvider
    return MockOfflineProvider(model_name=model)


__all__ = [
    "LLMProvider",
    "ProviderMessage",
    "ModelResponse",
    "ToolCall",
    "AnthropicProvider",
    "OpenAIProvider",
    "DeepSeekProvider",
    "OllamaProvider",
    "MockOfflineProvider",
    "get_provider",
]
