"""PARI Layer 1: Checkpoint Index Manager.

Architectural Purpose:
    Closes Pi F4 (O(N) JSONL replay latency on deep 500+ turn sessions).
    Periodically writes a CHECKPOINT index event (every 50 turns) containing the
    active context state, file snapshot manifests, and token metrics.
    Allows resuming a session by reading backward to the most recent checkpoint.
"""

from pathlib import Path
from typing import Any

from pari.session.logger import SessionLogger


_SKIPPED = frozenset(
    {
        "FILE_SNAPSHOT",
        "SNAPSHOT",
        "snapshot",
        "SESSION_START",
        "session_start",
        "CHECKPOINT_INDEX",
    }
)


class CheckpointManager:
    """Manages periodic checkpoint intervals for fast session resumption."""

    def __init__(self, logger: SessionLogger, interval_turns: int = 50):
        self.logger = logger
        self.interval_turns = interval_turns
        self._turns = 0

    def record_turn(self, state_snapshot: dict[str, Any]) -> str | None:
        """Increment turn counter and trigger checkpoint write if interval is met."""
        self._turns += 1
        if self._turns % self.interval_turns != 0:
            return None
        chain = self.logger.record_ids
        snapshot = dict(state_snapshot)
        snapshot["turns"] = self._turns
        return self.logger.append_event(
            "CHECKPOINT_INDEX",
            {
                "active_leaf_id": self.logger.last_record_id,
                "ancestor_chain": chain,
                "state": snapshot,
            },
        )

    def restore_turns(self, turns: int) -> None:
        """Set the turn count so the next checkpoint stays on the interval."""
        self._turns = turns

    def latest_checkpoint(self) -> dict[str, Any] | None:
        """Return the newest checkpoint record, scanning from the end of the log."""
        return self.logger.last_of_type("CHECKPOINT_INDEX")


def restore_transcript(
    events: list[dict[str, Any]],
    directory: Path | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Rebuild chat messages from the newest checkpoint, then the turns after it.

    With no checkpoint the whole log is replayed. ``turns`` counts user turns
    in the file, including ones already folded into the checkpoint.
    """
    checkpoint_at = _latest_checkpoint_index(events)
    if checkpoint_at is None:
        prior: list[dict[str, Any]] = []
        tail = events
    else:
        state = events[checkpoint_at].get("data", {}).get("state") or {}
        stored = state.get("messages")
        prior = []
        if isinstance(stored, list):
            prior = [item for item in stored if isinstance(item, dict)]
        tail = events[checkpoint_at + 1 :]
    messages = prior + _messages_from_events(tail, directory)
    return messages, _user_turns(events)


def _latest_checkpoint_index(events: list[dict[str, Any]]) -> int | None:
    for index in range(len(events) - 1, -1, -1):
        if events[index].get("type") == "CHECKPOINT_INDEX":
            return index
    return None


def _user_turns(events: list[dict[str, Any]]) -> int:
    return sum(1 for event in events if event.get("type") == "USER_TURN")


def _messages_from_events(
    events: list[dict[str, Any]],
    directory: Path | None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    index = 0
    while index < len(events):
        kind = events[index].get("type")
        if kind in _SKIPPED:
            index += 1
            continue
        if kind != "USER_TURN":
            index += 1
            continue
        data = events[index].get("data") or {}
        messages.append({"role": "user", "content": str(data.get("prompt", ""))})
        index += 1
        calls: list[dict[str, Any]] = []
        while index < len(events):
            current = events[index]
            current_kind = current.get("type")
            if current_kind in _SKIPPED:
                index += 1
                continue
            if current_kind == "TOOL_CALL":
                calls.append(_call_payload(current))
                index += 1
                continue
            if current_kind == "TOOL_RESULT" and calls:
                calls[-1]["output"] = _tool_output(current, directory)
                index += 1
                continue
            break
        for call in calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "name": call["name"],
                            "arguments": call["arguments"],
                        }
                    ],
                }
            )
            if call["output"] is not None:
                messages.append(
                    {
                        "role": "tool",
                        "content": call["output"],
                        "tool_call_id": call["id"],
                    }
                )
        if index < len(events) and events[index].get("type") == "ASSISTANT_TURN":
            text = events[index].get("data") or {}
            messages.append({"role": "assistant", "content": str(text.get("text", ""))})
            index += 1
    return messages


def _call_payload(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data") or {}
    arguments = data.get("arguments")
    return {
        "id": str(data.get("id") or event.get("id") or ""),
        "name": str(data.get("tool", "")),
        "arguments": arguments if isinstance(arguments, dict) else {},
        "output": None,
    }


def _tool_output(event: dict[str, Any], directory: Path | None) -> str:
    data = event.get("data") or {}
    output = data.get("output")
    if isinstance(output, str):
        return output
    relative = data.get("sidecar_path")
    if directory is None or not isinstance(relative, str):
        return ""
    path = directory / relative
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
