"""PARI Layer 1: Structured Session Event Types.

Defines all immutable event records logged into the append-only Merkle DAG.
Each event possesses a unique record ID, timestamp, and an optional parent_id
forming an unbroken causal Merkle chain.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, Optional
import uuid


class SessionEventType(str, Enum):
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
    """An individual event entry in the session Merkle DAG."""
    type: SessionEventType
    payload: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    crc32: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "type": self.type.value if isinstance(self.type, SessionEventType) else self.type,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "crc32": self.crc32,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionEvent":
        return cls(
            id=data["id"],
            parent_id=data.get("parent_id"),
            type=SessionEventType(data["type"]),
            timestamp=data["timestamp"],
            payload=data.get("payload", {}),
            crc32=data.get("crc32"),
        )
