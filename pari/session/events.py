"""PARI Layer 1: Structured Session Event Types.

Defines all immutable event records logged into the append-only Merkle DAG.
Each event possesses a unique record ID, timestamp, and an optional parent_id
forming an unbroken causal Merkle chain.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SessionEventType(StrEnum):
    SESSION_START = "session_start"
    USER_PROMPT = "user_prompt"
    ASSISTANT_RESPONSE = "assistant_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FILE_SNAPSHOT = "file_snapshot"
    CHECKPOINT = "checkpoint"
    SESSION_END = "session_end"


@dataclass
class SessionEvent:
    """An individual event entry in the session Merkle DAG.

    Fields:
        type: Event category
        payload: Event data dictionary
        id: Unique UUID identifier
        parent_id: ID of preceding causal event
        timestamp: Epoch timestamp
        crc32: Integrity checksum
    """

    type: SessionEventType
    payload: dict[str, Any]
    id: str | None = None
    parent_id: str | None = None
    timestamp: float = 0.0
    crc32: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to serializable dictionary."""
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionEvent":
        """Reconstruct event from serialized dictionary."""
        raise NotImplementedError
