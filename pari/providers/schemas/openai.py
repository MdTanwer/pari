"""OpenAI chat completions on the wire.

DeepSeek, Grok, and OpenRouter use the same shape. Provider fields we do not
read are ignored so a new field cannot break a call.
"""

import json
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pari.providers.exceptions import ProviderError, failure_from_payload
from pari.providers.message import ProviderMessage, ToolCall
from pari.providers.response import ModelResponse
from pari.providers.schemas.types import EMPTY_SCHEMA, TokenCount


class ChatFunction(BaseModel):
    """The function half of a chat-completions tool call."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    name: str = Field(default="", description="Tool name")
    arguments: str = Field(default="{}", description="JSON string of arguments")

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, value: object) -> str:
        return value if isinstance(value, str) else ""

    @field_validator("arguments", mode="before")
    @classmethod
    def _arguments(cls, value: object) -> str:
        """Some providers send an object instead of a JSON string."""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return json.dumps(value)
        return "{}"

    def parsed_arguments(self) -> dict[str, Any]:
        try:
            parsed = json.loads(self.arguments)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}


class ChatToolCall(BaseModel):
    """One entry of ``message.tool_calls`` in a chat-completions body."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    id: str = Field(default="", description="Tool call id")
    type: str = Field(default="function", description="Always function today")
    function: ChatFunction = Field(default_factory=ChatFunction)

    @field_validator("id", mode="before")
    @classmethod
    def _id(cls, value: object) -> str:
        return value if isinstance(value, str) else ""

    @field_validator("function", mode="before")
    @classmethod
    def _function(cls, value: object) -> object:
        return value if isinstance(value, (dict, ChatFunction)) else {}

    @classmethod
    def from_tool_call(cls, call: ToolCall) -> "ChatToolCall":
        return cls(
            id=call.id,
            function=ChatFunction(name=call.name, arguments=json.dumps(call.arguments)),
        )

    def to_tool_call(self) -> ToolCall:
        return ToolCall(
            id=self.id,
            name=self.function.name,
            arguments=self.function.parsed_arguments(),
        )


class ChatMessage(BaseModel):
    """One chat-completions message, in either direction."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    role: str = Field(default="assistant", description="system, user, assistant, tool")
    content: str | None = Field(default=None, description="Message text")
    tool_calls: list[ChatToolCall] | None = Field(
        default=None, description="Calls requested by the assistant"
    )
    tool_call_id: str | None = Field(
        default=None, description="Call this tool result answers"
    )

    @field_validator("content", mode="before")
    @classmethod
    def _content(cls, value: object) -> str | None:
        if value is None or isinstance(value, str):
            return value
        return ""

    @field_validator("tool_calls", mode="before")
    @classmethod
    def _tool_calls(cls, value: object) -> list[object] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, (dict, ChatToolCall))]

    @classmethod
    def from_provider_message(cls, message: ProviderMessage) -> "ChatMessage":
        """Tool calls stay structured so the model can answer them."""
        if message.role == "tool":
            return cls(
                role="tool",
                content=message.content,
                tool_call_id=message.tool_call_id or "",
            )
        calls = None
        if message.role == "assistant" and message.tool_calls:
            calls = [ChatToolCall.from_tool_call(call) for call in message.tool_calls]
        return cls(role=message.role, content=message.content, tool_calls=calls)


class ChatChoice(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    message: ChatMessage = Field(default_factory=ChatMessage)
    finish_reason: str | None = Field(default=None, description="Why output ended")

    @field_validator("message", mode="before")
    @classmethod
    def _message(cls, value: object) -> object:
        return value if isinstance(value, dict) else {}

    @field_validator("finish_reason", mode="before")
    @classmethod
    def _finish(cls, value: object) -> str | None:
        return value if isinstance(value, str) else None


class ChatUsage(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    prompt_tokens: TokenCount = Field(default=0, description="Prompt tokens")
    completion_tokens: TokenCount = Field(default=0, description="Completion tokens")


class ChatCompletion(BaseModel):
    """One successful chat-completions body."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    choices: list[ChatChoice] = Field(default_factory=list)
    usage: ChatUsage = Field(default_factory=ChatUsage)

    @field_validator("choices", mode="before")
    @classmethod
    def _choices(cls, value: object) -> list[object]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    @field_validator("usage", mode="before")
    @classmethod
    def _usage(cls, value: object) -> object:
        return value if isinstance(value, dict) else {}

    @classmethod
    def from_payload(cls, payload: object, provider: str) -> "ChatCompletion":
        if not isinstance(payload, dict):
            raise ProviderError(
                provider, detail="The model response was not a JSON object."
            )
        try:
            completion = cls.model_validate(payload)
        except ValidationError as exc:
            raise ProviderError(
                provider, detail="The model response did not match a chat completion."
            ) from exc
        if not completion.choices:
            raise failure_from_payload(
                provider, payload, default_detail="The model response had no choices."
            )
        return completion

    def to_model_response(self) -> ModelResponse:
        choice = self.choices[0] if self.choices else ChatChoice()
        calls = choice.message.tool_calls or []
        return ModelResponse(
            text=choice.message.content or "",
            tool_calls=[call.to_tool_call() for call in calls],
            tokens_in=self.usage.prompt_tokens,
            tokens_out=self.usage.completion_tokens,
            stop_reason=choice.finish_reason,
        )


class ChatFunctionDef(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    name: str = Field(..., description="Tool name")
    description: str = Field(default="", description="What the tool does")
    parameters: dict[str, Any] = Field(..., description="JSON Schema for arguments")


class ChatTool(BaseModel):
    """One entry of the request's ``tools`` list."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    type: str = Field(default="function")
    function: ChatFunctionDef

    @classmethod
    def from_schema(cls, tool: dict[str, Any]) -> "ChatTool":
        schema = tool.get("parameters")
        return cls(
            function=ChatFunctionDef(
                name=str(tool["name"]),
                description=str(tool.get("description") or ""),
                parameters=schema if isinstance(schema, dict) else EMPTY_SCHEMA,
            )
        )


class ChatCompletionRequest(BaseModel):
    """The body posted to a chat-completions endpoint."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    model: str = Field(..., description="Model id")
    temperature: float = Field(..., ge=0.0, description="Sampling temperature")
    max_tokens: int = Field(..., gt=0, description="Output token ceiling")
    messages: list[ChatMessage] = Field(..., description="Transcript to send")
    tools: list[ChatTool] | None = Field(default=None, description="Callable tools")

    @classmethod
    def from_turn(
        cls,
        model: str,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
    ) -> "ChatCompletionRequest":
        return cls(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[ChatMessage.from_provider_message(item) for item in messages],
            tools=[ChatTool.from_schema(tool) for tool in tools] if tools else None,
        )

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)
