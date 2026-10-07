"""Unit tests for pari.session append-only JSONL log and torn-write recovery."""

import json
from pathlib import Path
from pari.session import SessionLogger


def test_session_append_and_read(tmp_path: Path):
    session_file = tmp_path / "test_session.jsonl"
    logger = SessionLogger(session_file)

    id1 = logger.append_event("USER_TURN", {"prompt": "Fix bug"})
    id2 = logger.append_event("TOOL_CALL", {"tool": "file_edit"})

    assert logger.last_record_id == id2

    events = logger.read_events()
    assert len(events) == 2
    assert events[0]["id"] == id1
    assert events[0]["parentId"] is None
    assert events[1]["id"] == id2
    assert events[1]["parentId"] == id1
    assert "crc32" in events[0]


def test_torn_write_recovery(tmp_path: Path):
    session_file = tmp_path / "torn_session.jsonl"
    logger = SessionLogger(session_file)
    id1 = logger.append_event("USER_TURN", {"prompt": "Initial prompt"})

    # Simulate mid-write process kill: append incomplete corrupted line
    with open(session_file, "a", encoding="utf-8") as f:
        f.write('{"id": "incomplete-torn-record", "parentId": "')

    # Re-open session logger; verify it truncates corrupt trailing record
    new_logger = SessionLogger(session_file)
    assert new_logger.last_record_id == id1

    events = new_logger.read_events()
    assert len(events) == 1
    assert events[0]["id"] == id1
