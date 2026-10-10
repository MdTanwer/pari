"""PARI Multi-Provider LLM Integration Layer.

Sign in with an API key or an account token. The supported providers are
OpenAI, DeepSeek, Anthropic, Grok, and OpenRouter.
"""

import os

from pari.auth.login import NO_MODEL, resolve_secret, sign_in_hint
from pari.auth.providers import info_for_model
from pari.providers.anthropic import AnthropicProvider
from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage, ToolCall
from pari.providers.deepseek import DeepSeekProvider
from pari.providers.errors import ProviderError
from pari.providers.grok import GrokProvider
from pari.providers.mock import MockOfflineProvider
from pari.providers.openai import OpenAIProvider
from pari.providers.openrouter import OpenRouterProvider


_BUILDERS = {
    "openai": OpenAIProvider,
    "deepseek": DeepSeekProvider,
    "anthropic": AnthropicProvider,
    "grok": GrokProvider,
    "openrouter": OpenRouterProvider,
}


def get_provider(model_name: str | None = None) -> LLMProvider:
    """Pick a provider from the model name, the environment, and the saved sign-in.

    An explicit ``pari-core`` name stays the offline model. A call with no
    model raises when ``PARI_MODEL`` is unset and no Anthropic key is present.
    """
    chosen = (model_name or os.environ.get("PARI_MODEL") or "").strip()
    if chosen == "pari-core":
        return MockOfflineProvider()
    info = info_for_model(chosen) if chosen else None
    if info is None and not chosen and os.environ.get("ANTHROPIC_API_KEY"):
        info = info_for_model("claude")
        chosen = info.default_model if info is not None else ""
    if info is None:
        if not chosen:
            raise RuntimeError(NO_MODEL)
        raise NotImplementedError(f"No provider is implemented for {chosen}.")
    model = chosen if chosen != info.id else info.default_model
    key = resolve_secret(info)
    if not key:
        raise RuntimeError(sign_in_hint(info))
    builder = _BUILDERS[info.id]
    return builder(model, key)


__all__ = [
    "AnthropicProvider",
    "DeepSeekProvider",
    "GrokProvider",
    "LLMProvider",
    "MockOfflineProvider",
    "ModelResponse",
    "OpenAIProvider",
    "OpenRouterProvider",
    "ProviderError",
    "ProviderMessage",
    "ToolCall",
    "get_provider",
]
