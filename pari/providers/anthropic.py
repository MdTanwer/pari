"""PARI Providers: Anthropic Claude Adapter.

Supports Claude models through the Messages API, including tool calls.
"""

import os
from collections.abc import Callable
from typing import Any

import httpx

from pari.providers.base import LLMProvider
from pari.providers.exceptions import decode_body
from pari.providers.http import checked_post, iter_sse
from pari.providers.message import ProviderMessage
from pari.providers.response import ModelResponse
from pari.providers.schemas.anthropic import (
    AnthropicMessage,
    AnthropicRequest,
    _split_messages,
    _visible_text,
)
from pari.providers.stream import StreamBuild, feed_anthropic_line


_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_BETA_HEADER = "prompt-caching-2024-07-31"
_MAX_TOKENS = 4096
_LABEL = "Anthropic"


class AnthropicProvider(LLMProvider):
    """Adapter for the Anthropic Messages API."""

    def __init__(
        self,
        model_name: str = "claude-3-7-sonnet-20250219",
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        super().__init__(model_name, api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self._transport = transport

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        on_delta: Callable[[str], None] | None = None,
    ) -> ModelResponse:
        """Call the Messages API and return text plus any tool calls."""
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        request = AnthropicRequest.from_turn(
            self.model_name, messages, tools, temperature, _MAX_TOKENS
        )
        payload = request.to_payload()
        if on_delta is None:
            async with httpx.AsyncClient(transport=self._transport) as client:
                response = await checked_post(
                    client,
                    _API_URL,
                    headers=_headers(self.api_key),
                    payload=payload,
                    provider=_LABEL,
                )
            body = decode_body(response, _LABEL)
            return AnthropicMessage.from_payload(body, _LABEL).to_model_response()
        payload["stream"] = True
        build = StreamBuild()
        async with httpx.AsyncClient(transport=self._transport) as client:
            async for line in iter_sse(
                client,
                _API_URL,
                headers=_headers(self.api_key),
                payload=payload,
                provider=_LABEL,
            ):
                feed_anthropic_line(line, build, on_delta)
        return build.to_model_response()


def _headers(api_key: str) -> dict[str, str]:
    return {
        "x-api-key": api_key,
        "anthropic-version": _API_VERSION,
        "anthropic-beta": _BETA_HEADER,
        "content-type": "application/json",
    }


__all__ = ["AnthropicProvider", "_headers", "_split_messages", "_visible_text"]
