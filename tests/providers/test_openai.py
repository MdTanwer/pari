"""OpenAI-compatible chat completions for DeepSeek, Grok, and OpenRouter."""

import json

import httpx
import pytest

from pari.providers.deepseek import DeepSeekProvider
from pari.providers.exceptions import ProviderError
from pari.providers.grok import GrokProvider
from pari.providers.message import ProviderMessage, ToolCall
from pari.providers.openai import OpenAIProvider
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
                tool_calls=[
                    ToolCall(
                        id="call_1", name="read_file", arguments={"path": "app.py"}
                    )
                ],
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
    assert json.loads(messages[1]["tool_calls"][0]["function"]["arguments"]) == {
        "path": "app.py"
    }
    assert "[tools:" not in messages[1]["content"]
    assert messages[2]["role"] == "tool"
    assert messages[2]["tool_call_id"] == "call_1"


def _ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            "choices": [
                {"finish_reason": "stop", "message": {"content": "ok"}},
            ],
        },
    )


@pytest.mark.asyncio
async def test_read_error_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    async def instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("pari.providers.http.asyncio.sleep", instant)
    seen = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        if seen["n"] < 3:
            raise httpx.ReadError("connection reset")
        return _ok(request)

    provider = OpenAIProvider("gpt-4o", "sk-test", httpx.MockTransport(handler))
    response = await provider.complete([ProviderMessage(role="user", content="hi")])
    assert seen["n"] == 3
    assert response.text == "ok"


@pytest.mark.asyncio
async def test_http_rejection_hides_the_response_body():
    seen = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return httpx.Response(
            401,
            json={
                "error": {
                    "message": "Unauthorized",
                    "type": "rejected_by_access_enforcement",
                    "code": "no_matching_rule",
                },
                "status": 401,
            },
        )

    provider = OpenAIProvider("gpt-4o", "sk-test", httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        await provider.complete([ProviderMessage(role="user", content="read the repo")])
    error = caught.value
    assert error.status_code == 401
    assert error.code == "no_matching_rule"
    assert error.detail == "Unauthorized"
    assert error.error_type == "rejected_by_access_enforcement"
    assert str(error) == "Unauthorized"
    assert "{" not in str(error)
    assert seen["n"] == 1


@pytest.mark.asyncio
async def test_timeout_is_a_provider_error(monkeypatch: pytest.MonkeyPatch):
    async def instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("pari.providers.http.asyncio.sleep", instant)

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    provider = OpenAIProvider("gpt-4o", "sk-test", httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        await provider.complete([ProviderMessage(role="user", content="hi")])
    assert caught.value.kind == "timeout"
    assert "timed out" not in str(caught.value)


@pytest.mark.asyncio
async def test_length_stop_is_preserved():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": "cut"},
                    }
                ]
            },
        )

    provider = OpenAIProvider("gpt-4o", "sk-test", httpx.MockTransport(handler))
    response = await provider.complete([ProviderMessage(role="user", content="hi")])
    assert response.stop_reason == "length"
    assert response.text == "cut"
    assert response.tokens_in == 0
    assert response.tool_calls == []


@pytest.mark.asyncio
async def test_a_list_body_is_rejected():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["nope"])

    provider = OpenAIProvider("gpt-4o", "sk-test", httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        await provider.complete([ProviderMessage(role="user", content="hi")])
    assert caught.value.detail == "The model response was not a JSON object."
    assert "nope" not in str(caught.value)


@pytest.mark.asyncio
async def test_a_non_json_body_is_rejected():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>nope</html>")

    provider = OpenAIProvider("gpt-4o", "sk-test", httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        await provider.complete([ProviderMessage(role="user", content="hi")])
    assert caught.value.detail == "The model response was not JSON."
    assert "html" not in str(caught.value)
