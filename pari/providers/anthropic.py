"""PARI Providers: Anthropic Claude Adapter.

Supports Claude 3.7 Sonnet, Claude 3.5 Sonnet, and Claude 3.5 Haiku with prompt caching.
"""

import json
import os
from typing import Any, Dict, List, Optional
import httpx
from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage, ToolCall


class AnthropicProvider(LLMProvider):
    """Adapter for Anthropic Messages API."""

    def __init__(self, model_name: str = "claude-3-7-sonnet-20250219", api_key: Optional[str] = None):
        super().__init__(model_name, api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.api_url = "https://api.anthropic.com/v1/messages"

    async def complete(
        self,
        messages: List[ProviderMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        system_text = ""
        user_assistant_msgs = []

        for m in messages:
            if m.role == "system":
                system_text += m.content + "\n"
            else:
                user_assistant_msgs.append({"role": m.role, "content": m.content})

        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": user_assistant_msgs,
            "max_tokens": 4096,
            "temperature": temperature,
        }
        if system_text:
            payload["system"] = system_text
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.api_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Parse text and tool calls
        text_content = ""
        tool_calls = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        usage = data.get("usage", {})
        return ModelResponse(
            text=text_content,
            tool_calls=tool_calls,
            tokens_in=usage.get("input_tokens", 0),
            tokens_out=usage.get("output_tokens", 0),
            cached_tokens=usage.get("cache_read_input_tokens", 0),
            stop_reason=data.get("stop_reason"),
        )
