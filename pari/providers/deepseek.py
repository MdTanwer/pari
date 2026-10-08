"""PARI Providers: DeepSeek Adapter.

DeepSeek speaks the OpenAI chat completions API at its own host.
"""

import httpx

from pari.providers.openai_compat import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    """Adapter for the DeepSeek chat API."""

    def __init__(
        self,
        model_name: str = "deepseek-chat",
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        super().__init__(
            model_name,
            api_key,
            "https://api.deepseek.com/chat/completions",
            transport,
            missing_key_message=(
                "Sign in to DeepSeek: pari login deepseek --api-key <key> "
                "or pari login deepseek --account <token>."
            ),
        )
