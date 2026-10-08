"""PARI Providers: OpenAI Adapter.

Supports GPT-4o and the other OpenAI chat models with function calling.
"""

import httpx

from pari.providers.openai_compat import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    """Adapter for the OpenAI Chat Completions API."""

    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        super().__init__(
            model_name,
            api_key,
            "https://api.openai.com/v1/chat/completions",
            transport,
            missing_key_message=(
                "Sign in to OpenAI: pari login openai --api-key <key> "
                "or pari login openai --account <token>."
            ),
        )
