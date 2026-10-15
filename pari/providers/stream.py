"""Turn a provider's server-sent events into text deltas and one response.

The screen prints each text piece as it arrives. Tool calls are assembled
from the same events and returned when the stream ends.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pari.providers.message import ToolCall
from pari.providers.response import ModelResponse


@dataclass
class StreamBuild:
    """One streamed completion, filled in as events arrive."""

    text: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cached_tokens: int = 0
    stop_reason: str | None = None
    calls: list[dict[str, str]] = field(default_factory=list)

    def to_model_response(self) -> ModelResponse:
        return ModelResponse(
            text=self.text,
            tool_calls=[_tool_call(slot) for slot in self.calls if slot.get("name")],
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            cached_tokens=self.cached_tokens,
            stop_reason=self.stop_reason,
        )


def take_openai_delta(event: dict[str, Any], build: StreamBuild) -> str:
    """Apply one chat-completions chunk. Return the new text, if any."""
    usage = event.get("usage")
    if isinstance(usage, dict):
        build.tokens_in = _count(usage.get("prompt_tokens"), build.tokens_in)
        build.tokens_out = _count(usage.get("completion_tokens"), build.tokens_out)
    choices = event.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0] if isinstance(choices[0], dict) else {}
    reason = choice.get("finish_reason")
    if isinstance(reason, str) and reason:
        build.stop_reason = reason
    delta = choice.get("delta")
    if not isinstance(delta, dict):
        return ""
    _merge_openai_tools(build, delta.get("tool_calls"))
    piece = delta.get("content")
    if not isinstance(piece, str) or not piece:
        return ""
    build.text += piece
    return piece


def take_anthropic_event(event: dict[str, Any], build: StreamBuild) -> str:
    """Apply one Messages API event. Return the new text, if any."""
    kind = event.get("type")
    if kind == "message_start":
        message = event.get("message")
        usage = message.get("usage") if isinstance(message, dict) else None
        if isinstance(usage, dict):
            build.tokens_in = _count(usage.get("input_tokens"), build.tokens_in)
            build.cached_tokens = _count(
                usage.get("cache_read_input_tokens"), build.cached_tokens
            )
        return ""
    if kind == "content_block_start":
        block = event.get("content_block")
        if isinstance(block, dict) and block.get("type") == "tool_use":
            build.calls.append(
                {
                    "id": _str(block.get("id")),
                    "name": _str(block.get("name")),
                    "arguments": "",
                }
            )
        return ""
    if kind == "content_block_delta":
        return _anthropic_delta(event.get("delta"), build)
    if kind == "message_delta":
        delta = event.get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("stop_reason"), str):
            reason = delta["stop_reason"]
            build.stop_reason = "length" if reason == "max_tokens" else reason
        usage = event.get("usage")
        if isinstance(usage, dict):
            build.tokens_out = _count(usage.get("output_tokens"), build.tokens_out)
    return ""


def feed_openai_line(
    line: str, build: StreamBuild, on_delta: Callable[[str], None] | None
) -> None:
    """Apply one chat-completions SSE line and paint any new text now."""
    _feed(line, build, take_openai_delta, on_delta)


def feed_anthropic_line(
    line: str, build: StreamBuild, on_delta: Callable[[str], None] | None
) -> None:
    """Apply one Messages API SSE line and paint any new text now."""
    _feed(line, build, take_anthropic_event, on_delta)


def emit_openai_lines(
    lines: list[str], on_delta: Callable[[str], None] | None
) -> StreamBuild:
    """Replay chat-completions SSE lines."""
    build = StreamBuild()
    for line in lines:
        feed_openai_line(line, build, on_delta)
    return build


def emit_anthropic_lines(
    lines: list[str], on_delta: Callable[[str], None] | None
) -> StreamBuild:
    """Replay Messages API SSE lines."""
    build = StreamBuild()
    for line in lines:
        feed_anthropic_line(line, build, on_delta)
    return build


def _feed(
    line: str,
    build: StreamBuild,
    take: Callable[[dict[str, Any], StreamBuild], str],
    on_delta: Callable[[str], None] | None,
) -> None:
    event = _data_event(line)
    if event is None:
        return
    piece = take(event, build)
    if piece and on_delta is not None:
        on_delta(piece)


def _data_event(line: str) -> dict[str, Any] | None:
    if not line.startswith("data:"):
        return None
    raw = line.removeprefix("data:").strip()
    if not raw or raw == "[DONE]":
        return None
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) else None


def _anthropic_delta(delta: object, build: StreamBuild) -> str:
    if not isinstance(delta, dict):
        return ""
    if delta.get("type") == "text_delta":
        piece = delta.get("text")
        if not isinstance(piece, str) or not piece:
            return ""
        build.text += piece
        return piece
    if delta.get("type") == "input_json_delta" and build.calls:
        partial = delta.get("partial_json")
        if isinstance(partial, str):
            build.calls[-1]["arguments"] += partial
    return ""


def _merge_openai_tools(build: StreamBuild, calls: object) -> None:
    if not isinstance(calls, list):
        return
    for call in calls:
        if not isinstance(call, dict):
            continue
        index = call.get("index")
        slot = index if isinstance(index, int) and index >= 0 else len(build.calls)
        while len(build.calls) <= slot:
            build.calls.append({"id": "", "name": "", "arguments": ""})
        current = build.calls[slot]
        if isinstance(call.get("id"), str) and call["id"]:
            current["id"] = call["id"]
        function = call.get("function")
        if not isinstance(function, dict):
            continue
        if isinstance(function.get("name"), str):
            current["name"] += function["name"]
        if isinstance(function.get("arguments"), str):
            current["arguments"] += function["arguments"]


def _tool_call(slot: dict[str, str]) -> ToolCall:
    try:
        parsed = json.loads(slot["arguments"] or "{}")
    except json.JSONDecodeError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    return ToolCall(id=slot["id"] or "call_0", name=slot["name"], arguments=parsed)


def _count(value: object, current: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return current
    return value


def _str(value: object) -> str:
    return value if isinstance(value, str) else ""
