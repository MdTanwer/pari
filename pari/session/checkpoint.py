"""PARI Layer 1: Checkpoint Index Manager.

Architectural Purpose:
    Closes Pi F4 (O(N) JSONL replay latency on deep 500+ turn sessions).
    Periodically writes a CHECKPOINT index event (every 50 turns) containing the
    active context state, file snapshot manifests, and token metrics.
    Allows resuming a session by reading backward to the most recent checkpoint.
"""

from typing import Any

from pari.session.logger import SessionLogger


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
        return self.logger.append_event(
            "CHECKPOINT_INDEX",
            {
                "active_leaf_id": self.logger.last_record_id,
                "ancestor_chain": chain,
                "state": state_snapshot,
            },
        )

    def latest_checkpoint(self) -> dict[str, Any] | None:
        """Return the newest checkpoint record, scanning from the end of the log."""
        for record in reversed(self.logger.read_events()):
            if record["type"] == "CHECKPOINT_INDEX":
                return record
        return None
