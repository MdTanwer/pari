"""PARI Providers: Base LLM Interface.

Defines the contract for calling LLM inference APIs with tool calling and prompt caching.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ProviderMessage:
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    cache_control: bool = False


@dataclass
class ModelResponse:
    text: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cached_tokens: int = 0
    stop_reason: Optional[str] = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """Abstract base class for all LLM backend adapters."""

    def __init__(self, model_name: str, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key

    @abstractmethod
    async def complete(
        self,
        messages: List[ProviderMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Execute a completion request."""
        raise NotImplementedError
