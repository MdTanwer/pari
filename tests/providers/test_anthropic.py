"""Anthropic provider request and response mapping."""

import json

import httpx
import pytest

from pari.providers import get_provider
from pari.providers.anthropic import AnthropicProvider
from pari.providers.exceptions import ProviderError
from pari.providers.message import ProviderMessage, ToolCall
from pari.providers.mock import MockOfflineProvider


def _transport(status: int, payload: dict) -> httpx.MockTransport:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_complete_parses_text_and_tool_use():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode())
        seen["key"] = request.headers.get("x-api-key")
        return httpx.Response(
            200,
            json={
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 12, "output_tokens": 4},
                "content": [
                    {"type": "text", "text": "running"},
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "bash",
                        "input": {"command": "pwd"},
                    },
                ],
            },
        )

    provider = AnthropicProvider(
        "claude-test", "test-key", httpx.MockTransport(handler)
    )
    response = await provider.complete(
        [
            ProviderMessage(role="system", content="be brief"),
            ProviderMessage(role="user", content="where am I"),
        ],
        tools=[
            {
                "name": "bash",
                "description": "run a command",
                "parameters": {"type": "object", "properties": {}},
            }
        ],
    )
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "claude-test"
    assert body["system"] == [
        {"type": "text", "text": "be brief", "cache_control": {"type": "ephemeral"}}
    ]
    assert body["messages"][0]["role"] == "user"
    assert body["tools"][0]["input_schema"]["type"] == "object"
    assert seen["key"] == "test-key"
    assert response.text == "running"
    assert response.tool_calls[0].name == "bash"
    assert response.tool_calls[0].arguments == {"command": "pwd"}
    assert response.stop_reason == "tool_use"
    assert response.tokens_in == 12


@pytest.mark.asyncio
async def test_max_tokens_is_a_length_stop():
    payload = {
        "stop_reason": "max_tokens",
        "usage": {"input_tokens": 1, "output_tokens": 2},
        "content": [{"type": "text", "text": "cut"}],
    }
    provider = AnthropicProvider("claude-test", "test-key", _transport(200, payload))
    response = await provider.complete(
        [ProviderMessage(role="user", content="write a long file")]
    )
    assert response.stop_reason == "length"
    assert response.text == "cut"


@pytest.mark.asyncio
async def test_missing_key_refuses_the_call(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = AnthropicProvider("claude-test", api_key=None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        await provider.complete([ProviderMessage(role="user", content="hi")])


def test_get_provider_refuses_without_a_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("PARI_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="No model selected"):
        get_provider()


def test_pari_core_stays_offline_when_a_key_is_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    provider = get_provider("pari-core")
    assert isinstance(provider, MockOfflineProvider)


@pytest.mark.asyncio
async def test_http_rejection_is_a_provider_error():
    payload = {"error": {"message": "bad model", "type": "not_found_error"}}
    provider = AnthropicProvider("claude-test", "test-key", _transport(404, payload))
    with pytest.raises(ProviderError) as caught:
        await provider.complete([ProviderMessage(role="user", content="hi")])
    assert caught.value.status_code == 404
    assert caught.value.detail == "bad model"
    assert caught.value.error_type == "not_found_error"
    assert str(caught.value) == "bad model"


@pytest.mark.asyncio
async def test_a_list_body_is_rejected():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["nope"])

    provider = AnthropicProvider(
        "claude-test", "test-key", httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderError) as caught:
        await provider.complete([ProviderMessage(role="user", content="hi")])
    assert caught.value.detail == "The model response was not a JSON object."
    assert "nope" not in str(caught.value)


def test_get_provider_selects_anthropic(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    provider = get_provider("claude-3-7-sonnet-20250219")
    assert isinstance(provider, AnthropicProvider)
    assert provider.api_key == "test-key"


@pytest.mark.asyncio
async def test_a_200_error_body_is_the_providers_message():
    payload = {
        "type": "error",
        "error": {"type": "overloaded_error", "message": "Overloaded"},
    }
    provider = AnthropicProvider("claude-test", "test-key", _transport(200, payload))
    with pytest.raises(ProviderError) as caught:
        await provider.complete([ProviderMessage(role="user", content="hi")])
    assert caught.value.detail == "Overloaded"
    assert caught.value.error_type == "overloaded_error"


@pytest.mark.asyncio
async def test_tool_round_trip_and_prompt_caching():
    request_bodies: list[dict[str, object]] = []
    request_headers: list[httpx.Headers] = []
    cache_store: set[str] = set()

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        request_bodies.append(body)
        request_headers.append(request.headers)

        cache_key = json.dumps(
            {"system": body.get("system"), "messages": body.get("messages")}
        )
        is_cached = cache_key in cache_store
        cache_store.add(cache_key)

        cache_read = 50 if is_cached else 0
        tokens_in = 10 if is_cached else 60

        return httpx.Response(
            200,
            json={
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": tokens_in,
                    "output_tokens": 10,
                    "cache_read_input_tokens": cache_read,
                },
                "content": [{"type": "text", "text": "result processed"}],
            },
        )

    provider = AnthropicProvider(
        "claude-3-7-sonnet-20250219", "test-key", httpx.MockTransport(handler)
    )

    messages = [
        ProviderMessage(role="system", content="You are a helpful assistant."),
        ProviderMessage(role="user", content="check directory"),
        ProviderMessage(
            role="assistant",
            content="checking",
            tool_calls=[
                ToolCall(id="toolu_123", name="bash", arguments={"command": "ls"})
            ],
        ),
        ProviderMessage(
            role="tool",
            content="file1.txt\nfile2.txt",
            tool_call_id="toolu_123",
        ),
    ]

    resp1 = await provider.complete(messages)
    assert resp1.cached_tokens == 0
    assert resp1.tokens_in == 60

    body1 = request_bodies[0]
    assert request_headers[0].get("anthropic-beta") == "prompt-caching-2024-07-31"
    assert body1["system"] == [
        {
            "type": "text",
            "text": "You are a helpful assistant.",
            "cache_control": {"type": "ephemeral"},
        }
    ]

    chat = body1["messages"]
    assert len(chat) == 3
    assert chat[0]["role"] == "user"
    assert chat[1]["role"] == "assistant"
    asst_blocks = chat[1]["content"]
    assert asst_blocks[0] == {"type": "text", "text": "checking"}
    assert asst_blocks[1] == {
        "type": "tool_use",
        "id": "toolu_123",
        "name": "bash",
        "input": {"command": "ls"},
    }

    assert chat[2]["role"] == "user"
    tool_blocks = chat[2]["content"]
    assert tool_blocks[0]["type"] == "tool_result"
    assert tool_blocks[0]["tool_use_id"] == "toolu_123"
    assert tool_blocks[0]["content"] == "file1.txt\nfile2.txt"
    assert tool_blocks[0]["cache_control"] == {"type": "ephemeral"}

    resp2 = await provider.complete(messages)
    assert resp2.cached_tokens > 0
    assert resp2.cached_tokens == 50
