"""PARI Layer 1: Checkpoint Index Manager.

Architectural Purpose:
    Closes Pi F4 (O(N) JSONL replay latency on deep 500+ turn sessions).
    Periodically writes a CHECKPOINT index event (every 50 turns) containing the
    active context state, file snapshot manifests, and token metrics.
    Allows resuming a session by reading backward to the most recent checkpoint.
"""

from typing import Any, Dict, Optional
from pari.session.events import SessionEventType
from pari.session.logger import SessionLogger


class CheckpointManager:
    """Manages periodic checkpoint intervals for fast session resumption."""

    def __init__(self, logger: SessionLogger, interval_turns: int = 50):
        self.logger = logger
        self.interval_turns = interval_turns
        self.turn_count = 0

    def record_turn(self, state_snapshot: Dict[str, Any]) -> Optional[str]:
        """Increment turn counter and trigger checkpoint write if interval is met."""
        self.turn_count += 1
        if self.turn_count % self.interval_turns == 0:
            checkpoint_event = self.logger.log(
                SessionEventType.CHECKPOINT,
                payload={
                    "turn_index": self.turn_count,
                    "state": state_snapshot,
                },
            )
            return checkpoint_event.id
        return None
