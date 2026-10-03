"""PARI Providers: Local Ollama Adapter.

Supports local models (Llama 3, Qwen 2.5 Coder, DeepSeek R1 distilled) via local HTTP endpoint.
Allows 100% offline, private coding agent execution without external cloud tokens.
"""

from typing import Optional
from pari.providers.openai import OpenAIProvider


class OllamaProvider(OpenAIProvider):
    """Adapter for locally hosted Ollama instances."""

    def __init__(self, model_name: str = "qwen2.5-coder:7b", base_url: str = "http://localhost:11434/v1"):
        super().__init__(model_name, api_key="ollama")
        self.api_url = f"{base_url.rstrip('/')}/chat/completions"
