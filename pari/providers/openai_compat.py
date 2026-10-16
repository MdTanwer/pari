"""Chat completions client shared by OpenAI, DeepSeek, Grok, and OpenRouter."""

from collections.abc import Callable
from typing import Any

import httpx

from pari.providers.base import LLMProvider
from pari.providers.exceptions import decode_body
from pari.providers.http import checked_post, iter_sse
from pari.providers.message import ProviderMessage
from pari.providers.response import ModelResponse
from pari.providers.schemas.openai import ChatCompletion, ChatCompletionRequest
from pari.providers.stream import StreamBuild, feed_openai_line


_MAX_TOKENS = 4096


class OpenAICompatibleProvider(LLMProvider):
    """One request shape. The base URL is what changes per provider."""

    def __init__(
        self,
        model_name: str,
        api_key: str | None,
        base_url: str,
        transport: httpx.BaseTransport | None = None,
        missing_key_message: str = "API key is not set.",
        provider_label: str = "Model provider",
    ):
        super().__init__(model_name, api_key)
        self.base_url = base_url
        self._transport = transport
        self._missing_key_message = missing_key_message
        self._provider_label = provider_label

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        on_delta: Callable[[str], None] | None = None,
    ) -> ModelResponse:
        if not self.api_key:
            raise RuntimeError(self._missing_key_message)
        request = ChatCompletionRequest.from_turn(
            self.model_name, messages, tools, temperature, _MAX_TOKENS
        )
        payload = request.to_payload()
        headers = {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        if on_delta is None:
            async with httpx.AsyncClient(transport=self._transport) as client:
                response = await checked_post(
                    client,
                    self.base_url,
                    headers=headers,
                    payload=payload,
                    provider=self._provider_label,
                )
            body = decode_body(response, self._provider_label)
            return ChatCompletion.from_payload(
                body, self._provider_label
            ).to_model_response()
        payload["stream"] = True
        build = StreamBuild()
        async with httpx.AsyncClient(transport=self._transport) as client:
            async for line in iter_sse(
                client,
                self.base_url,
                headers=headers,
                payload=payload,
                provider=self._provider_label,
            ):
                feed_openai_line(line, build, on_delta)
        return build.to_model_response()
