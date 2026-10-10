"""Field types shared by the provider wire models."""

from typing import Annotated, Any

from pydantic import BeforeValidator, Field


def _count(value: object) -> int:
    """A missing, negative, or non-integer count is zero, not a failed call."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


TokenCount = Annotated[int, BeforeValidator(_count), Field(ge=0)]

EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}
