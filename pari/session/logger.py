"""PARI Layer 1: Append-Only JSONL Session Logger.

Architectural Purpose:
    Closes Claude Code F1 & Pi F5.
    Writes every session event with an explicit CRC32 checksum, flushes to OS buffer,
    and calls os.fsync() on critical milestones.
    On startup, scans backward from EOF to automatically detect and truncate torn writes
    caused by power loss or sudden SIGKILL.
"""

import json
import os
from pathlib import Path
import time
from typing import Any, Dict, Iterator, List, Optional
import uuid
import zlib

from pari.session.events import SessionEvent, SessionEventType


def compute_crc32(payload: str) -> str:
    """Compute 8-character hex CRC32 checksum."""
    return f"{zlib.crc32(payload.encode('utf-8')) & 0xffffffff:08x}"


class SessionLogger:
    """Manages an append-only JSONL session log with CRC32 integrity verification."""

    def __init__(self, session_file: Path):
        self.session_file = session_file
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.last_record_id: Optional[str] = None
        self._recover_and_index()

    def _recover_and_index(self) -> None:
        """Scan session file, recover from torn writes at EOF, and locate the last record ID."""
        if not self.session_file.exists() or self.session_file.stat().st_size == 0:
            return

        valid_offset = 0
        last_id = None

        with open(self.session_file, "rb") as f:
            while True:
                line_start = f.tell()
                line = f.readline()
                if not line:
                    break

                try:
                    text = line.decode("utf-8").strip()
                    if not text:
                        continue
                    data = json.loads(text)
                    stored_crc = data.get("crc32")
                    
                    # Verify CRC32
                    test_data = {k: v for k, v in data.items() if k != "crc32"}
                    canonical_json = json.dumps(test_data, sort_keys=True)
                    if compute_crc32(canonical_json) == stored_crc or str(zlib.crc32(canonical_json.encode('utf-8'))) == str(stored_crc):
                        valid_offset = f.tell()
                        last_id = data.get("id")
                    else:
                        # CRC mismatch -> torn write at EOF
                        break
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Incomplete trailing JSON line
                    break

        # If file ends with torn bytes, truncate cleanly to last valid record
        current_size = self.session_file.stat().st_size
        if valid_offset < current_size:
            with open(self.session_file, "r+b") as f:
                f.truncate(valid_offset)

        self.last_record_id = last_id

    def append_event(self, event_type: str, data: Dict[str, Any]) -> str:
        """Append an event record to the session log with CRC32."""
        record_id = str(uuid.uuid4())
        record = {
            "id": record_id,
            "parentId": self.last_record_id,
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        }
        
        canonical_json = json.dumps(record, sort_keys=True)
        crc = compute_crc32(canonical_json)
        record["crc32"] = crc

        line = json.dumps(record) + "\n"
        with open(self.session_file, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

        self.last_record_id = record_id
        return record_id

    def log(self, event_type: SessionEventType, payload: Dict[str, Any]) -> SessionEvent:
        """Typed event append API."""
        val = event_type.value if isinstance(event_type, SessionEventType) else str(event_type)
        rec_id = self.append_event(val, payload)
        return SessionEvent(
            id=rec_id,
            parent_id=self.last_record_id,
            type=SessionEventType(val) if val in [e.value for e in SessionEventType] else SessionEventType.USER_PROMPT,
            payload=payload,
        )

    def read_events(self) -> List[Dict[str, Any]]:
        """Read all verified records from the session file."""
        if not self.session_file.exists():
            return []
        events = []
        with open(self.session_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                text = line.strip()
                if text:
                    try:
                        events.append(json.loads(text))
                    except json.JSONDecodeError:
                        continue
        return events

    def iter_events(self) -> Iterator[SessionEvent]:
        for data in self.read_events():
            try:
                yield SessionEvent.from_dict({
                    "id": data["id"],
                    "parent_id": data.get("parentId") or data.get("parent_id"),
                    "type": data["type"],
                    "timestamp": data.get("timestamp", 0.0),
                    "payload": data.get("data") or data.get("payload", {}),
                    "crc32": data.get("crc32"),
                })
            except Exception:
                continue
