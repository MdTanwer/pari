"""PARI Tools: Base Interfaces and JSON Schema Definitions.

Converts Python tool implementations into standard OpenAI/Anthropic compatible
tool call schemas.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]

    def to_schema(self) -> dict[str, Any]:
        """Format definition as standard tool calling schema."""
        raise NotImplementedError


class Tool(ABC):
    """Abstract base class for all agent-callable tools."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Tool metadata and argument JSON schema."""
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute tool action safely."""
        pass
