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
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pari.session.events import SessionEvent, SessionEventType, checksum, new_event_id


_SIDECAR_LIMIT = 512


class SessionLogger:
    """Manages an append-only JSONL session log with CRC32 integrity verification."""

    def __init__(self, session_file: Path, spool_dir: Path | None = None):
        self.session_file = session_file
        self.spool_dir = spool_dir
        self.last_record_id: str | None = None
        self._ids: list[str] = []
        self._recover_and_index()

    @property
    def record_ids(self) -> list[str]:
        return list(self._ids)

    def _recover_and_index(self) -> None:
        """Drop a torn trailing record, then remember the surviving chain."""
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.session_file.exists():
            self.session_file.touch()
        raw = self.session_file.read_bytes()
        kept, records = _valid_records(raw)
        if kept != raw:
            with self.session_file.open("r+b") as handle:
                handle.truncate(len(kept))
                os.fsync(handle.fileno())
        self._ids = [record["id"] for record in records]
        self.last_record_id = self._ids[-1] if self._ids else None

    def log(
        self, event_type: SessionEventType | str, payload: dict[str, Any]
    ) -> SessionEvent:
        """Append a new verified session event to disk with CRC32 checksum."""
        if isinstance(event_type, SessionEventType):
            name = event_type.value
        else:
            name = event_type
        record = self._write_record(name, payload)
        return SessionEvent.from_dict(record)

    def append_event(self, event_type: str, data: dict[str, Any]) -> str:
        """Append one JSONL record and return its id."""
        return self._write_record(event_type, data)["id"]

    def last_of_type(self, event_type: str) -> dict[str, Any] | None:
        """Return the newest valid record of this type, reading from the end."""
        for record in _records_from_end(self.session_file):
            if record.get("type") == event_type:
                return record
        return None

    def _write_record(self, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        event_id = new_event_id()
        payload = _spill_output(event_id, dict(data), spool_dir=self.spool_dir)
        record = {
            "id": event_id,
            "parentId": self.last_record_id,
            "type": event_type,
            "timestamp": _now(),
            "data": payload,
        }
        record["crc32"] = checksum(record)
        line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
        fd = os.open(
            self.session_file,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o644,
        )
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        self._ids.append(event_id)
        self.last_record_id = event_id
        return record

    def read_events(self) -> list[dict[str, Any]]:
        """Read all verified records from the session file."""
        raw = self.session_file.read_bytes()
        _kept, records = _valid_records(raw)
        return records

    def iter_events(self) -> Iterator[SessionEvent]:
        """Iterate over all valid events in chronological order."""
        for record in self.read_events():
            yield SessionEvent.from_dict(record)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _spill_output(
    event_id: str,
    payload: dict[str, Any],
    spool_dir: Path | None = None,
) -> dict:
    output = payload.get("output")
    if not isinstance(output, str) or len(output.encode("utf-8")) <= _SIDECAR_LIMIT:
        return payload
    # The workspace spool is the one sidecar directory. Without it, the log
    # keeps the text instead of growing a second tree beside the session.
    if spool_dir is None:
        return payload
    spool_dir.mkdir(parents=True, exist_ok=True)
    path = spool_dir / f"{event_id}.txt"
    path.write_text(output, encoding="utf-8")
    payload.pop("output")
    payload["sidecar_path"] = str(path)
    return payload


def _records_from_end(path: Path) -> Iterator[dict[str, Any]]:
    """Yield checksum-valid records from the end of the file."""
    try:
        handle = path.open("rb")
    except OSError:
        return
    with handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        pending = b""
        while position > 0:
            step = min(65536, position)
            position -= step
            handle.seek(position)
            pending = handle.read(step) + pending
            lines = pending.split(b"\n")
            pending = lines[0]
            for line in reversed(lines[1:]):
                record = _parse_line(line)
                if record is not None:
                    yield record
        record = _parse_line(pending)
        if record is not None:
            yield record


def _valid_records(raw: bytes) -> tuple[bytes, list[dict[str, Any]]]:
    """Return the prefix of complete, checksum-valid lines and their records."""
    if not raw:
        return b"", []
    parts = raw.split(b"\n")
    complete = parts[:-1]
    kept_lines: list[bytes] = []
    records: list[dict[str, Any]] = []
    for line in complete:
        record = _parse_line(line)
        if record is None:
            break
        kept_lines.append(line)
        records.append(record)
    if not kept_lines:
        return b"", []
    return b"\n".join(kept_lines) + b"\n", records


def _parse_line(line: bytes) -> dict[str, Any] | None:
    if not line.strip():
        return None
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict) or "crc32" not in record or "id" not in record:
        return None
    if checksum(record) != record["crc32"]:
        return None
    return record
