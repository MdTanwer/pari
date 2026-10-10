"""Anthropic Messages API on the wire.

Provider fields we do not read are ignored so a new field cannot break a call.
"""

from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pari.providers.exceptions import ProviderError
from pari.providers.message import ProviderMessage, ToolCall
from pari.providers.response import ModelResponse


_EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}
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

    input_tokens: int = Field(default=0, ge=0, description="Prompt tokens")
    output_tokens: int = Field(default=0, ge=0, description="Completion tokens")
    cache_read_input_tokens: int = Field(
        default=0, ge=0, description="Prompt tokens read from the cache"
    )

    @field_validator(
        "input_tokens", "output_tokens", "cache_read_input_tokens", mode="before"
    )
    @classmethod
    def _count(cls, value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return 0
        return value


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
    content: str = Field(..., description="Message text")

    @classmethod
    def from_provider_message(cls, message: ProviderMessage) -> "AnthropicChatMessage":
        role = "assistant" if message.role == "assistant" else "user"
        return cls(role=role, content=_visible_text(message))


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
            input_schema=schema if isinstance(schema, dict) else _EMPTY_SCHEMA,
        )


class AnthropicRequest(BaseModel):
    """The body posted to the Messages API."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    model: str = Field(..., description="Model id")
    max_tokens: int = Field(..., gt=0, description="Output token ceiling")
    temperature: float = Field(..., ge=0.0, description="Sampling temperature")
    messages: list[AnthropicChatMessage] = Field(..., min_length=1)
    system: str | None = Field(default=None, description="Top-level system text")
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
        """System text is a top-level field. Anthropic rejects a system role."""
        system = "\n".join(
            m.content for m in messages if m.role == "system" and m.content
        )
        chat = [
            AnthropicChatMessage.from_provider_message(m)
            for m in messages
            if m.role != "system"
        ]
        if not chat:
            chat = [AnthropicChatMessage(role="user", content="Continue.")]
        return cls(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=chat,
            system=system or None,
            tools=[AnthropicTool.from_schema(t) for t in tools] if tools else None,
        )

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


def _visible_text(message: ProviderMessage) -> str:
    """Tool results already come back as the next user message from the loop."""
    if not message.tool_calls:
        return message.content or "."
    names = ", ".join(call.name for call in message.tool_calls)
    if message.content:
        return f"{message.content}\n[tools: {names}]"
    return f"[tools: {names}]"
