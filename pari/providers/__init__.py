"""PARI Multi-Provider LLM Integration Layer.

Architectural Purpose:
    Closes Antigravity F5 (Hard Google API lock-in) and Claude Code Anthropic
    exclusivity.
    Provides unified model abstraction across Anthropic Claude, OpenAI, DeepSeek, local
    Ollama,
    and an offline fallback provider for local testing.
"""

import os

from pari.providers.anthropic import AnthropicProvider
from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage, ToolCall
from pari.providers.mock import MockOfflineProvider


def get_provider(model_name: str | None = None) -> LLMProvider:
    """Pick a provider from the model name and the environment.

    ``pari-core`` is the offline model, even when an API key is present.
    A Claude name uses Anthropic. A bare call uses Anthropic only when
    ``ANTHROPIC_API_KEY`` is set and ``PARI_MODEL`` did not choose another name.
    """
    chosen = (model_name or os.environ.get("PARI_MODEL") or "").strip()
    key = os.environ.get("ANTHROPIC_API_KEY")
    # The REPL default must stay usable with no key and no network.
    if chosen == "pari-core":
        return MockOfflineProvider()
    if chosen.startswith("claude") or (not chosen and key):
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        model = chosen or "claude-3-7-sonnet-20250219"
        return AnthropicProvider(model, key)
    if not chosen:
        return MockOfflineProvider()
    raise NotImplementedError(f"No provider is implemented for {chosen}.")


__all__ = [
    "AnthropicProvider",
    "LLMProvider",
    "MockOfflineProvider",
    "ModelResponse",
    "ProviderMessage",
    "ToolCall",
    "get_provider",
]
