"""Unit tests for pari.session append-only JSONL log and torn-write recovery."""

import json
import time
from pathlib import Path

import pytest

from pari.session import (
    CheckpointManager,
    SessionDAG,
    SessionLogger,
    default_session_dir,
)
from pari.session.checkpoint import restore_transcript


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


def test_restore_uses_the_latest_checkpoint_and_the_tail(tmp_path: Path):
    logger = SessionLogger(tmp_path / "resume.jsonl")
    logger.append_event("USER_TURN", {"prompt": "old"})
    logger.append_event("ASSISTANT_TURN", {"text": "old answer"})
    checkpoints = CheckpointManager(logger, interval_turns=1)
    checkpoints.record_turn(
        {"messages": [{"role": "user", "content": "from-checkpoint"}]}
    )
    logger.append_event("USER_TURN", {"prompt": "new"})
    logger.append_event("TOOL_CALL", {"tool": "bash", "id": "c1", "arguments": {}})
    logger.append_event("FILE_SNAPSHOT", {"path": "a.py"})
    logger.append_event("TOOL_RESULT", {"tool": "bash", "output": "ok"})
    logger.append_event("ASSISTANT_TURN", {"text": "new answer"})

    messages, turns = restore_transcript(logger.read_events(), tmp_path)
    contents = [message["content"] for message in messages]
    assert "from-checkpoint" in contents
    assert "old" not in contents
    assert "new" in contents
    assert "ok" in contents
    assert "new answer" in contents
    assert turns == 2


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


def test_log_returns_the_record_it_wrote(tmp_path: Path):
    logger = SessionLogger(tmp_path / "written.jsonl")
    event = logger.log("USER_TURN", {"prompt": "hello"})
    assert event.payload["prompt"] == "hello"
    assert event.id == logger.last_record_id
    assert event.crc32 == logger.read_events()[-1]["crc32"]


def test_log_stays_linear(tmp_path: Path):
    baseline = _log_seconds(tmp_path / "baseline.jsonl", 200)
    elapsed = _log_seconds(tmp_path / "scaled.jsonl", 2_000)
    assert elapsed < max(baseline * 30, 5)


def test_append_event_ten_thousand_is_linear(tmp_path: Path):
    baseline = _append_seconds(tmp_path / "baseline.jsonl", 1_000)
    logger = SessionLogger(tmp_path / "many.jsonl")
    started = time.perf_counter()
    for index in range(10_000):
        logger.append_event("USER_TURN", {"prompt": str(index)})
    elapsed = time.perf_counter() - started
    assert len(logger.record_ids) == 10_000
    assert elapsed < max(baseline * 25, 10)


def test_latest_checkpoint_reads_past_a_torn_tail(tmp_path: Path):
    logger = SessionLogger(tmp_path / "tail.jsonl")
    checkpoints = CheckpointManager(logger, interval_turns=1)
    logger.append_event("USER_TURN", {"prompt": "one"})
    checkpoint_id = checkpoints.record_turn({"n": 1})
    logger.append_event("USER_TURN", {"prompt": "after"})
    with logger.session_file.open("a", encoding="utf-8") as handle:
        handle.write('{"id": "torn"')

    stored = checkpoints.latest_checkpoint()
    assert stored is not None
    assert stored["id"] == checkpoint_id


def test_default_session_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PARI_SESSION_DIR", raising=False)
    # Global default in ~/.pari/sessions
    global_dir = default_session_dir()
    assert str(global_dir).startswith(str(Path.home()))
    assert ".pari" in str(global_dir)

    # Project workspace default under ~/.pari/projects/<slug>/sessions
    ws_dir = default_session_dir(tmp_path)
    assert str(ws_dir).startswith(str(Path.home()))
    assert ".pari" in str(ws_dir)
    assert tmp_path.name in str(ws_dir)
    assert not (tmp_path / ".pari").exists()

    # Environment override via PARI_SESSION_DIR
    custom = tmp_path / "custom_sessions"
    monkeypatch.setenv("PARI_SESSION_DIR", str(custom))
    assert default_session_dir() == custom
    assert default_session_dir(tmp_path) == custom


def _log_seconds(path: Path, count: int) -> float:
    logger = SessionLogger(path)
    started = time.perf_counter()
    for index in range(count):
        logger.log("USER_TURN", {"prompt": str(index)})
    return time.perf_counter() - started


def _append_seconds(path: Path, count: int) -> float:
    logger = SessionLogger(path)
    started = time.perf_counter()
    for index in range(count):
        logger.append_event("USER_TURN", {"prompt": str(index)})
    return time.perf_counter() - started
