"""PARI Tools: Base Interfaces and JSON Schema Definitions.

Converts Python tool implementations into standard OpenAI/Anthropic compatible
tool call schemas.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]

    def to_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class Tool(ABC):
    """Abstract base class for all agent-callable tools."""

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        pass
