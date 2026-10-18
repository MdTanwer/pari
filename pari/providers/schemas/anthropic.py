"""Anthropic Messages API on the wire.

Provider fields we do not read are ignored so a new field cannot break a call.
"""

from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pari.providers.exceptions import ProviderError, failure_from_payload
from pari.providers.message import ProviderMessage, ToolCall
from pari.providers.response import ModelResponse
from pari.providers.schemas.types import EMPTY_SCHEMA, TokenCount


_BLOCK_TYPES = ("text", "tool_use")


class TextBlock(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    type: Literal["text"] = "text"
    text: str = Field(default="", description="Assistant text")

    @field_validator("text", mode="before")
    @classmethod
    def _text(cls, value: object) -> str:
        return value if isinstance(value, str) else ""


class ToolUseBlock(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    type: Literal["tool_use"] = "tool_use"
    id: str = Field(default="", description="Tool use id")
    name: str = Field(default="", description="Tool name")
    input: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")

    @field_validator("id", "name", mode="before")
    @classmethod
    def _label(cls, value: object) -> str:
        return value if isinstance(value, str) else ""

    @field_validator("input", mode="before")
    @classmethod
    def _input(cls, value: object) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def to_tool_call(self) -> ToolCall:
        return ToolCall(id=self.id, name=self.name, arguments=dict(self.input))


ContentBlock = Annotated[TextBlock | ToolUseBlock, Field(discriminator="type")]


class AnthropicUsage(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    input_tokens: TokenCount = Field(default=0, description="Prompt tokens")
    output_tokens: TokenCount = Field(default=0, description="Completion tokens")
    cache_read_input_tokens: TokenCount = Field(
        default=0, description="Prompt tokens read from the cache"
    )
    cache_creation_input_tokens: TokenCount = Field(
        default=0, description="Prompt tokens written to the cache"
    )


class AnthropicMessage(BaseModel):
    """One successful Messages API body."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    stop_reason: str | None = Field(default=None, description="Why output ended")
    usage: AnthropicUsage = Field(default_factory=AnthropicUsage)
    content: list[ContentBlock] = Field(default_factory=list)

    @field_validator("stop_reason", mode="before")
    @classmethod
    def _stop(cls, value: object) -> str | None:
        return value if isinstance(value, str) else None

    @field_validator("usage", mode="before")
    @classmethod
    def _usage(cls, value: object) -> object:
        return value if isinstance(value, dict) else {}

    @field_validator("content", mode="before")
    @classmethod
    def _content(cls, value: object) -> list[object]:
        if not isinstance(value, list):
            return []
        return [
            item
            for item in value
            if isinstance(item, dict) and item.get("type") in _BLOCK_TYPES
        ]

    @classmethod
    def from_payload(cls, payload: object, provider: str) -> "AnthropicMessage":
        if not isinstance(payload, dict):
            raise ProviderError(
                provider, detail="The model response was not a JSON object."
            )
        if payload.get("type") == "error":
            raise failure_from_payload(provider, payload)
        try:
            return cls.model_validate(payload)
        except ValidationError as exc:
            raise ProviderError(
                provider, detail="The model response did not match a message."
            ) from exc

    def to_model_response(self) -> ModelResponse:
        # The loop treats "length" as a cut-off tool call and does not run it.
        stop = "length" if self.stop_reason == "max_tokens" else self.stop_reason
        return ModelResponse(
            text="".join(b.text for b in self.content if isinstance(b, TextBlock)),
            tool_calls=[
                b.to_tool_call() for b in self.content if isinstance(b, ToolUseBlock)
            ],
            tokens_in=self.usage.input_tokens,
            tokens_out=self.usage.output_tokens,
            cached_tokens=self.usage.cache_read_input_tokens,
            stop_reason=stop,
        )


class AnthropicChatMessage(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str | list[dict[str, Any]] = Field(
        ..., description="Message text or content blocks"
    )

    @classmethod
    def from_provider_message(cls, message: ProviderMessage) -> "AnthropicChatMessage":
        role = "assistant" if message.role == "assistant" else "user"
        if message.role == "assistant":
            blocks: list[dict[str, Any]] = []
            if message.content:
                blocks.append({"type": "text", "text": message.content})
            if message.tool_calls:
                for call in message.tool_calls:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": call.id,
                            "name": call.name,
                            "input": call.arguments,
                        }
                    )
            if not blocks:
                blocks.append({"type": "text", "text": message.content or "."})
            return cls(role="assistant", content=blocks)
        if message.role == "tool":
            return cls(
                role="user",
                content=[
                    {
                        "type": "tool_result",
                        "tool_use_id": message.tool_call_id or "",
                        "content": message.content,
                    }
                ],
            )
        return cls(
            role=role, content=[{"type": "text", "text": message.content or "."}]
        )


class AnthropicTool(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    name: str = Field(..., description="Tool name")
    description: str = Field(default="", description="What the tool does")
    input_schema: dict[str, Any] = Field(..., description="JSON Schema for input")

    @classmethod
    def from_schema(cls, tool: dict[str, Any]) -> "AnthropicTool":
        schema = tool.get("parameters") or tool.get("input_schema")
        return cls(
            name=str(tool["name"]),
            description=str(tool.get("description") or ""),
            input_schema=schema if isinstance(schema, dict) else EMPTY_SCHEMA,
        )


def _split_messages(
    messages: list[ProviderMessage],
) -> tuple[list[dict[str, Any]] | None, list[AnthropicChatMessage]]:
    """Pull system text out with cache_control. Convert chat messages to blocks."""
    system_parts = [m.content for m in messages if m.role == "system" and m.content]
    system: list[dict[str, Any]] | None = None
    if system_parts:
        system = [
            {
                "type": "text",
                "text": "\n".join(system_parts),
                "cache_control": {"type": "ephemeral"},
            }
        ]

    chat_messages = [m for m in messages if m.role != "system"]
    if not chat_messages:
        chat_messages = [ProviderMessage(role="user", content="Continue.")]

    last_stable_idx = None
    for idx, msg in enumerate(chat_messages):
        if msg.cache_control:
            last_stable_idx = idx

    if last_stable_idx is None:
        last_stable_idx = len(chat_messages) - 1

    chat: list[AnthropicChatMessage] = []

    for idx, msg in enumerate(chat_messages):
        is_stable = idx == last_stable_idx
        if msg.role == "assistant":
            blocks: list[dict[str, Any]] = []
            if msg.content:
                blocks.append({"type": "text", "text": msg.content})
            if msg.tool_calls:
                for call in msg.tool_calls:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": call.id,
                            "name": call.name,
                            "input": call.arguments,
                        }
                    )
            if not blocks:
                blocks.append({"type": "text", "text": msg.content or "."})
            if is_stable:
                blocks[-1]["cache_control"] = {"type": "ephemeral"}
            chat.append(AnthropicChatMessage(role="assistant", content=blocks))

        elif msg.role == "tool":
            tool_block: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": msg.tool_call_id or "",
                "content": msg.content,
            }
            if is_stable:
                tool_block["cache_control"] = {"type": "ephemeral"}

            if chat and chat[-1].role == "user" and isinstance(chat[-1].content, list):
                chat[-1].content.append(tool_block)
            else:
                chat.append(AnthropicChatMessage(role="user", content=[tool_block]))

        else:  # role == "user"
            user_blocks = [{"type": "text", "text": msg.content or "."}]
            if is_stable:
                user_blocks[-1]["cache_control"] = {"type": "ephemeral"}
            chat.append(AnthropicChatMessage(role="user", content=user_blocks))

    return system, chat


class AnthropicRequest(BaseModel):
    """The body posted to the Messages API."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    model: str = Field(..., description="Model id")
    max_tokens: int = Field(..., gt=0, description="Output token ceiling")
    temperature: float = Field(..., ge=0.0, description="Sampling temperature")
    messages: list[AnthropicChatMessage] = Field(..., min_length=1)
    system: list[dict[str, Any]] | str | None = Field(
        default=None, description="Top-level system text"
    )
    tools: list[AnthropicTool] | None = Field(default=None, description="Tools")

    @classmethod
    def from_turn(
        cls,
        model: str,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
    ) -> "AnthropicRequest":
        system, chat = _split_messages(messages)
        return cls(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=chat,
            system=system,
            tools=[AnthropicTool.from_schema(t) for t in tools] if tools else None,
        )

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


def _visible_text(message: ProviderMessage) -> str:
    """Format message text and tool call summaries for display."""
    if not message.tool_calls:
        return message.content or "."
    names = ", ".join(call.name for call in message.tool_calls)
    if message.content:
        return f"{message.content}\n[tools: {names}]"
    return f"[tools: {names}]"
