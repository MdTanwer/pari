"""PARI Layer 1: Structured Session Event Types.

Defines all immutable event records logged into the append-only Merkle DAG.
Each event possesses a unique record ID, timestamp, and an optional parent_id
forming an unbroken causal Merkle chain.
"""

import json
import os
import time
import zlib
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
    """An individual event entry in the session Merkle DAG."""

    type: SessionEventType | str
    payload: dict[str, Any]
    id: str | None = None
    parent_id: str | None = None
    timestamp: str = ""
    crc32: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to the on-disk JSONL record."""
        event_type = (
            self.type.value if isinstance(self.type, SessionEventType) else self.type
        )
        record = {
            "id": self.id,
            "parentId": self.parent_id,
            "type": event_type,
            "timestamp": self.timestamp,
            "data": self.payload,
        }
        if self.crc32 is not None:
            record["crc32"] = self.crc32
        return record

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionEvent":
        """Reconstruct event from a serialized record."""
        raw_type = data["type"]
        try:
            event_type: SessionEventType | str = SessionEventType(raw_type)
        except ValueError:
            event_type = raw_type
        return cls(
            type=event_type,
            payload=data.get("data", {}),
            id=data.get("id"),
            parent_id=data.get("parentId"),
            timestamp=data.get("timestamp", ""),
            crc32=data.get("crc32"),
        )


def new_event_id() -> str:
    """Return a time-sortable UUIDv7 string."""
    unix_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    high = (unix_ms << 16) | 0x7000 | rand_a
    low = (0b10 << 62) | rand_b
    raw = high.to_bytes(8, "big") + low.to_bytes(8, "big")
    hex_id = raw.hex()
    head = f"{hex_id[:8]}-{hex_id[8:12]}-{hex_id[12:16]}"
    tail = f"{hex_id[16:20]}-{hex_id[20:]}"
    return f"{head}-{tail}"


def checksum(record: dict[str, Any]) -> str:
    """CRC32 of the record with the crc32 field removed."""
    body = {key: value for key, value in record.items() if key != "crc32"}
    encoded = json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return f"{zlib.crc32(encoded) & 0xFFFFFFFF:08x}"
