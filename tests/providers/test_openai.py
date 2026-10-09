"""OpenAI-compatible chat completions for DeepSeek, Grok, and OpenRouter."""

import json

import httpx
import pytest

from pari.providers.base import ProviderMessage, ToolCall
from pari.providers.deepseek import DeepSeekProvider
from pari.providers.grok import GrokProvider
from pari.providers.openrouter import OpenRouterProvider


def test_each_provider_has_its_own_host():
    assert DeepSeekProvider("deepseek-chat", "k").base_url.startswith(
        "https://api.deepseek.com/"
    )
    assert GrokProvider("grok-3", "k").base_url.startswith("https://api.x.ai/")
    assert OpenRouterProvider("openrouter/openai/gpt-4o-mini", "k").base_url.startswith(
        "https://openrouter.ai/"
    )


@pytest.mark.asyncio
async def test_complete_parses_a_tool_call():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": "listing",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {
                                        "name": "bash",
                                        "arguments": '{"command": "pwd"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    provider = DeepSeekProvider("deepseek-chat", "ds-key", httpx.MockTransport(handler))
    response = await provider.complete(
        [ProviderMessage(role="user", content="where am I")],
        tools=[
            {
                "name": "bash",
                "description": "run",
                "parameters": {"type": "object"},
            }
        ],
    )
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "deepseek-chat"
    assert body["tools"][0]["function"]["name"] == "bash"
    assert seen["auth"] == "Bearer ds-key"
    assert response.text == "listing"
    assert response.tool_calls[0].arguments == {"command": "pwd"}
    assert response.tokens_in == 5


@pytest.mark.asyncio
async def test_tool_results_stay_structured():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "done"},
                    }
                ],
            },
        )

    provider = DeepSeekProvider("deepseek-chat", "ds-key", httpx.MockTransport(handler))
    await provider.complete(
        [
            ProviderMessage(role="user", content="read app.py"),
            ProviderMessage(
                role="assistant",
                content="reading",
                tool_calls=[ToolCall("call_1", "read_file", {"path": "app.py"})],
            ),
            ProviderMessage(
                role="tool",
                content="def add():\n    return 1\n",
                tool_call_id="call_1",
            ),
        ]
    )
    body = seen["body"]
    assert isinstance(body, dict)
    messages = body["messages"]
    assert messages[1]["tool_calls"][0]["function"]["name"] == "read_file"
    assert "[tools:" not in messages[1]["content"]
    assert messages[2]["role"] == "tool"
    assert messages[2]["tool_call_id"] == "call_1"
