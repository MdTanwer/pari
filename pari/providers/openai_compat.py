"""Chat completions client shared by OpenAI, DeepSeek, Grok, and OpenRouter."""

import json
from typing import Any

import httpx

from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage, ToolCall


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
    ):
        super().__init__(model_name, api_key)
        self.base_url = base_url
        self._transport = transport
        self._missing_key_message = missing_key_message

    async def complete(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        if not self.api_key:
            raise RuntimeError(self._missing_key_message)
        payload: dict[str, Any] = {
            "model": self.model_name,
            "temperature": temperature,
            "max_tokens": _MAX_TOKENS,
            "messages": [_message(item) for item in messages],
        }
        converted = _tools(tools)
        if converted:
            payload["tools"] = converted
        async with httpx.AsyncClient(transport=self._transport) as client:
            response = await client.post(
                self.base_url,
                headers={
                    "authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Provider request failed ({response.status_code}): {response.text}"
            )
        return _parse(response.json())


def _message(message: ProviderMessage) -> dict[str, Any]:
    """One chat message. Tool calls stay structured so the model can answer them."""
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id or "",
            "content": message.content or "",
        }
    role = message.role if message.role in ("system", "assistant") else "user"
    payload: dict[str, Any] = {"role": role, "content": message.content or ""}
    if role == "assistant" and message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                },
            }
            for call in message.tool_calls
        ]
    return payload


def _tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not tools:
        return []
    converted = []
    for tool in tools:
        schema = tool.get("parameters") or {"type": "object", "properties": {}}
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": schema,
                },
            }
        )
    return converted


def _parse(payload: dict[str, Any]) -> ModelResponse:
    choices = payload.get("choices") or []
    message: dict[str, Any] = {}
    finish = None
    if choices and isinstance(choices[0], dict):
        raw = choices[0].get("message")
        if isinstance(raw, dict):
            message = raw
        finish = choices[0].get("finish_reason")
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    stop = "length" if finish == "length" else finish
    return ModelResponse(
        text=str(message.get("content") or ""),
        tool_calls=_calls(message.get("tool_calls")),
        tokens_in=int(usage.get("prompt_tokens") or 0),
        tokens_out=int(usage.get("completion_tokens") or 0),
        stop_reason=str(stop) if stop is not None else None,
    )


def _calls(raw: object) -> list[ToolCall]:
    if not isinstance(raw, list):
        return []
    calls: list[ToolCall] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        function = item.get("function")
        if not isinstance(function, dict):
            function = {}
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments)
            except json.JSONDecodeError:
                parsed = {}
        elif isinstance(arguments, dict):
            parsed = arguments
        else:
            parsed = {}
        calls.append(
            ToolCall(
                id=str(item.get("id") or ""),
                name=str(function.get("name") or ""),
                arguments=parsed,
            )
        )
    return calls
