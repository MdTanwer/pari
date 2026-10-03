"""PARI Providers: DeepSeek Adapter.

Supports DeepSeek V3 and DeepSeek R1 via OpenAI-compatible API endpoint.
High performance, cost-effective editor tier model ($0.27/M input, $1.10/M output).
"""

import os
from typing import Optional
from pari.providers.openai import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """Adapter for DeepSeek API using OpenAI-compatible interface."""

    def __init__(self, model_name: str = "deepseek-chat", api_key: Optional[str] = None):
        super().__init__(model_name, api_key or os.environ.get("DEEPSEEK_API_KEY"))
        self.api_url = "https://api.deepseek.com/chat/completions"
