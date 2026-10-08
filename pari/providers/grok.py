"""PARI Providers: Grok Adapter.

Grok speaks the OpenAI chat completions API at api.x.ai.
"""

import httpx

from pari.providers.openai_compat import OpenAICompatibleProvider


class GrokProvider(OpenAICompatibleProvider):
    """Adapter for the xAI Grok chat API."""

    def __init__(
        self,
        model_name: str = "grok-3",
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        super().__init__(
            model_name,
            api_key,
            "https://api.x.ai/v1/chat/completions",
            transport,
            missing_key_message=(
                "Sign in to Grok: pari login grok --api-key <key> "
                "or pari login grok --account <token>."
            ),
        )
