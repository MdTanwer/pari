"""PARI Providers: OpenRouter Adapter.

OpenRouter speaks the OpenAI chat completions API and routes the model id.
"""

import httpx

from pari.providers.openai_compat import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    """Adapter for the OpenRouter chat API."""

    def __init__(
        self,
        model_name: str = "openrouter/openai/gpt-4o-mini",
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        super().__init__(
            model_name,
            api_key,
            "https://openrouter.ai/api/v1/chat/completions",
            transport,
            missing_key_message=(
                "Sign in to OpenRouter: pari login openrouter --api-key <key> "
                "or pari login openrouter --account <token>."
            ),
        )
