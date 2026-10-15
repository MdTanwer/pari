"""Stream parsers turn provider events into text the screen can paint."""

import httpx
import pytest

from pari.providers.message import ProviderMessage
from pari.providers.openai import OpenAIProvider
from pari.providers.stream import emit_anthropic_lines, emit_openai_lines


def test_openai_stream_paints_text_then_keeps_the_tool_call():
    seen: list[str] = []
    lines = [
        'data: {"choices":[{"delta":{"content":"Look"},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{"content":" here"},"finish_reason":null}]}',
        (
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1",'
            '"function":{"name":"bash","arguments":"{\\"command\\": \\"pwd\\"}"}}]},'
            '"finish_reason":"tool_calls"}]}'
        ),
        "data: [DONE]",
    ]
    built = emit_openai_lines(lines, seen.append)
    assert seen == ["Look", " here"]
    assert built.text == "Look here"
    assert built.calls[0]["name"] == "bash"
    assert built.to_model_response().tool_calls[0].arguments == {"command": "pwd"}
    assert built.stop_reason == "tool_calls"


def test_anthropic_stream_paints_text_deltas():
    seen: list[str] = []
    lines = [
        (
            'data: {"type":"content_block_delta","delta":'
            '{"type":"text_delta","text":"Hi"}}'
        ),
        (
            'data: {"type":"content_block_delta","delta":{"type":"text_delta",'
            '"text":" there"}}'
        ),
        (
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},'
            '"usage":{"output_tokens":4}}'
        ),
    ]
    built = emit_anthropic_lines(lines, seen.append)
    assert seen == ["Hi", " there"]
    assert built.text == "Hi there"
    assert built.stop_reason == "end_turn"
    assert built.tokens_out == 4


class _TwoChunks(httpx.AsyncByteStream):
    def __init__(self, order: list[str]) -> None:
        self._order = order

    async def __aiter__(self):
        self._order.append("first-chunk")
        yield (
            b'data: {"choices":[{"delta":{"content":"One"},"finish_reason":null}]}\n\n'
        )
        self._order.append("second-chunk")
        yield (
            b'data: {"choices":[{"delta":{"content":" two"},'
            b'"finish_reason":"stop"}]}\n\n'
        )


class _StreamTransport(httpx.AsyncBaseTransport):
    def __init__(self, order: list[str]) -> None:
        self._order = order

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, stream=_TwoChunks(self._order))


@pytest.mark.asyncio
async def test_text_is_painted_before_the_rest_of_the_stream_arrives():
    order: list[str] = []
    provider = OpenAIProvider("gpt-4o", "key", transport=_StreamTransport(order))
    response = await provider.complete(
        [ProviderMessage(role="user", content="hi")],
        on_delta=order.append,
    )
    assert order.index("One") < order.index("second-chunk")
    assert response.text == "One two"
