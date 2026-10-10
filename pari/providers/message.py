"""Messages and tool calls in the form the agent loop sends to any provider."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """One tool call. The id links the call to its tool result."""

    id: str = Field(..., description="Tool call id from the provider")
    name: str = Field(..., description="Tool name")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments, already parsed from JSON"
    )


class ProviderMessage(BaseModel):
    """One transcript entry, independent of the provider's wire format."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(default="", description="Text of the message")
    tool_calls: list[ToolCall] | None = Field(
        default=None, description="Calls the assistant asked to run"
    )
    tool_call_id: str | None = Field(
        default=None, description="Call this tool result answers"
    )
    cache_control: bool = Field(
        default=False, description="Mark this message as a prompt-cache breakpoint"
    )
