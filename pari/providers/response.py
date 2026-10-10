"""ModelResponse: one completion, independent of the provider."""

from pydantic import BaseModel, Field

from pari.providers.message import ToolCall


__all__ = ["ModelResponse"]


class ModelResponse(BaseModel):
    """Result of one completion request.

    ``stop_reason`` is ``"length"`` when the output was cut off. The loop does
    not run tool calls from a cut-off response.
    """

    text: str = Field(default="", description="Assistant text")
    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Tool calls the model asked to run"
    )
    tokens_in: int = Field(default=0, ge=0, description="Prompt tokens")
    tokens_out: int = Field(default=0, ge=0, description="Completion tokens")
    cached_tokens: int = Field(
        default=0, ge=0, description="Prompt tokens read from the provider cache"
    )
    stop_reason: str | None = Field(
        default=None, description="Normalized stop reason, such as length or stop"
    )

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0
