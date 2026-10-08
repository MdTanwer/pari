"""The providers a person can sign in to.

Radius is not one of them. Each entry is an API the agent calls directly.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    label: str
    env: str
    default_model: str
    base_url: str | None
    prefixes: tuple[str, ...]


PROVIDERS: tuple[ProviderInfo, ...] = (
    ProviderInfo(
        "openai",
        "OpenAI",
        "OPENAI_API_KEY",
        "gpt-4o",
        "https://api.openai.com/v1/chat/completions",
        ("gpt-", "gpt4", "o1", "o3", "o4", "chatgpt"),
    ),
    ProviderInfo(
        "deepseek",
        "DeepSeek",
        "DEEPSEEK_API_KEY",
        "deepseek-chat",
        "https://api.deepseek.com/chat/completions",
        ("deepseek",),
    ),
    ProviderInfo(
        "anthropic",
        "Anthropic",
        "ANTHROPIC_API_KEY",
        "claude-3-7-sonnet-20250219",
        None,
        ("claude",),
    ),
    ProviderInfo(
        "grok",
        "Grok",
        "XAI_API_KEY",
        "grok-3",
        "https://api.x.ai/v1/chat/completions",
        ("grok",),
    ),
    ProviderInfo(
        "openrouter",
        "OpenRouter",
        "OPENROUTER_API_KEY",
        "openrouter/openai/gpt-4o-mini",
        "https://openrouter.ai/api/v1/chat/completions",
        ("openrouter/", "or/"),
    ),
)

_BY_ID = {item.id: item for item in PROVIDERS}


def get_info(provider_id: str) -> ProviderInfo:
    info = _BY_ID.get(provider_id.strip().lower())
    if info is None:
        names = ", ".join(item.id for item in PROVIDERS)
        raise ValueError(f"Unknown provider '{provider_id}'. Choose one of: {names}.")
    return info


def info_for_model(model_name: str) -> ProviderInfo | None:
    """Match a model id to a provider. A provider id uses that provider's default."""
    name = model_name.strip().lower()
    direct = _BY_ID.get(name)
    if direct is not None:
        return direct
    for info in PROVIDERS:
        if name.startswith(info.prefixes):
            return info
    return None
