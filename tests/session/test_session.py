"""Unit tests for pari.session append-only JSONL log and torn-write recovery."""

import json
from pathlib import Path

from pari.session import CheckpointManager, SessionDAG, SessionLogger


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


def test_bad_checksum_is_truncated(tmp_path: Path):
    session_file = tmp_path / "checksum.jsonl"
    logger = SessionLogger(session_file)
    kept = logger.append_event("USER_TURN", {"prompt": "keep"})
    record = {
        "id": "forged",
        "parentId": kept,
        "type": "TOOL_CALL",
        "timestamp": "2026-10-03T09:00:00.000Z",
        "data": {"tool": "bash"},
        "crc32": "00000000",
    }
    with session_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")

    recovered = SessionLogger(session_file)
    assert recovered.last_record_id == kept
    assert len(recovered.read_events()) == 1


def test_checkpoint_records_ancestor_chain(tmp_path: Path):
    logger = SessionLogger(tmp_path / "checkpoint.jsonl")
    checkpoints = CheckpointManager(logger, interval_turns=2)
    first = logger.append_event("USER_TURN", {"prompt": "one"})
    assert checkpoints.record_turn({"turn": 1}) is None
    second = logger.append_event("TOOL_CALL", {"tool": "bash"})
    checkpoint_id = checkpoints.record_turn({"turn": 2})

    stored = checkpoints.latest_checkpoint()
    assert stored is not None
    assert stored["id"] == checkpoint_id
    assert stored["data"]["ancestor_chain"] == [first, second]
    assert stored["parentId"] == second


def test_lineage_follows_parent_pointers(tmp_path: Path):
    logger = SessionLogger(tmp_path / "dag.jsonl")
    logger.append_event("USER_TURN", {"prompt": "one"})
    logger.append_event("TOOL_CALL", {"tool": "bash"})
    graph = SessionDAG()
    for event in logger.iter_events():
        graph.add_event(event)
    lineage = graph.get_lineage()
    labels = []
    for event in lineage:
        if event.type == "USER_TURN":
            labels.append(event.payload["prompt"])
        else:
            labels.append(event.payload["tool"])
    assert labels == ["one", "bash"]
