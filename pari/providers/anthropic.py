"""PARI Providers: Anthropic Claude Adapter.

Supports Claude models through the Messages API, including tool calls.
"""

import os
from typing import Any

import httpx

from pari.providers.base import LLMProvider
from pari.providers.exceptions import decode_body
from pari.providers.http import checked_post
from pari.providers.message import ProviderMessage
from pari.providers.response import ModelResponse
from pari.providers.schemas.anthropic import AnthropicMessage, AnthropicRequest


_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
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
    ) -> ModelResponse:
        """Call the Messages API and return text plus any tool calls."""
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        request = AnthropicRequest.from_turn(
            self.model_name, messages, tools, temperature, _MAX_TOKENS
        )
        async with httpx.AsyncClient(transport=self._transport) as client:
            response = await checked_post(
                client,
                _API_URL,
                headers=_headers(self.api_key),
                payload=request.to_payload(),
                provider=_LABEL,
            )
        body = decode_body(response, _LABEL)
        return AnthropicMessage.from_payload(body, _LABEL).to_model_response()


def _headers(api_key: str) -> dict[str, str]:
    return {
        "x-api-key": api_key,
        "anthropic-version": _API_VERSION,
        "content-type": "application/json",
    }
