"""PARI Providers: OpenAI Adapter.

Supports GPT-4o, o3-mini, and GPT-4.5 with function calling.
"""

import json
import os
from typing import Any, Dict, List, Optional
import httpx
from pari.providers.base import LLMProvider, ModelResponse, ProviderMessage, ToolCall


class OpenAIProvider(LLMProvider):
    """Adapter for OpenAI Chat Completions API."""

    def __init__(self, model_name: str = "gpt-4o", api_key: Optional[str] = None):
        super().__init__(model_name, api_key or os.environ.get("OPENAI_API_KEY"))
        self.api_url = "https://api.openai.com/v1/chat/completions"

    async def complete(
        self,
        messages: List[ProviderMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        formatted_msgs = []
        for m in messages:
            formatted_msgs.append({"role": m.role, "content": m.content})

        headers = {
            "Authorization": f"Bearer {self.api_key or ''}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": formatted_msgs,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.api_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        text_content = msg.get("content") or ""

        tool_calls = []
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=args,
                )
            )

        usage = data.get("usage", {})
        return ModelResponse(
            text=text_content,
            tool_calls=tool_calls,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            stop_reason=choice.get("finish_reason"),
        )
