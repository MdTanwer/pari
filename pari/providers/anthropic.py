"""PARI Providers: Anthropic Claude Adapter.

Supports Claude models through the Messages API, including tool calls.
"""

import os
from typing import Any

import httpx

from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage, ToolCall
from pari.providers.errors import checked_post


_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_MAX_TOKENS = 4096


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
        payload = _request_body(self.model_name, messages, tools, temperature)
        async with httpx.AsyncClient(transport=self._transport) as client:
            response = await checked_post(
                client,
                _API_URL,
                headers=_headers(self.api_key),
                payload=payload,
                provider="Anthropic",
            )
        return _parse_response(response.json())


def _headers(api_key: str) -> dict[str, str]:
    return {
        "x-api-key": api_key,
        "anthropic-version": _API_VERSION,
        "content-type": "application/json",
    }


def _request_body(
    model: str,
    messages: list[ProviderMessage],
    tools: list[dict[str, Any]] | None,
    temperature: float,
) -> dict[str, Any]:
    system, chat = _split_messages(messages)
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": _MAX_TOKENS,
        "temperature": temperature,
        "messages": chat,
    }
    if system:
        body["system"] = system
    converted = _tools(tools)
    if converted:
        body["tools"] = converted
    return body


def _split_messages(
    messages: list[ProviderMessage],
) -> tuple[str, list[dict[str, str]]]:
    """Pull system text out. Anthropic does not accept a system role in messages."""
    system_parts: list[str] = []
    chat: list[dict[str, str]] = []
    for message in messages:
        if message.role == "system":
            if message.content:
                system_parts.append(message.content)
            continue
        role = "assistant" if message.role == "assistant" else "user"
        chat.append({"role": role, "content": _visible_text(message)})
    if not chat:
        chat.append({"role": "user", "content": "Continue."})
    return "\n".join(system_parts), chat


def _visible_text(message: ProviderMessage) -> str:
    """Keep history as plain text so a later user turn stays a valid message.

    Tool results already come back as the next user message from the loop.
    """
    text = message.content
    if not message.tool_calls:
        return text or "."
    names = ", ".join(call.name for call in message.tool_calls)
    if text:
        return f"{text}\n[tools: {names}]"
    return f"[tools: {names}]"


def _tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not tools:
        return []
    converted: list[dict[str, Any]] = []
    for tool in tools:
        schema = tool.get("parameters") or tool.get("input_schema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        converted.append(
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": schema,
            }
        )
    return converted


def _parse_response(payload: dict[str, Any]) -> ModelResponse:
    texts: list[str] = []
    calls: list[ToolCall] = []
    for block in payload.get("content") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            texts.append(str(block.get("text") or ""))
        elif block.get("type") == "tool_use":
            arguments = block.get("input")
            if not isinstance(arguments, dict):
                arguments = {}
            calls.append(
                ToolCall(
                    id=str(block.get("id") or ""),
                    name=str(block.get("name") or ""),
                    arguments=arguments,
                )
            )
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    stop = payload.get("stop_reason")
    # The loop treats "length" as a cut-off tool call and does not run it.
    if stop == "max_tokens":
        stop = "length"
    return ModelResponse(
        text="".join(texts),
        tool_calls=calls,
        tokens_in=int(usage.get("input_tokens") or 0),
        tokens_out=int(usage.get("output_tokens") or 0),
        cached_tokens=int(usage.get("cache_read_input_tokens") or 0),
        stop_reason=str(stop) if stop is not None else None,
    )
