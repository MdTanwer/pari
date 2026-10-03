"""PARI Layer 4: Double-While Execution Loop.

Architectural Purpose:
    Outer loop: Session conversation interaction (waiting for user input).
    Inner loop: Autonomous tool-calling turns until task is resolved or user feedback needed.
    Continuation Guard: If the model's stop_reason == "length" (e.g. output truncated),
    automatically prompts a continuation message rather than executing broken partial syntax.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class TurnResult:
    response_text: str
    tool_calls_executed: int
    tokens_used: int
    requires_user_input: bool


class AgentExecutionLoop:
    """Manages the autonomous double-while execution loop."""

    def __init__(self, max_autonomous_turns: int = 25):
        self.max_autonomous_turns = max_autonomous_turns

    async def run_turn(
        self,
        prompt: str,
        step_fn: Callable[[str, int], Any],
        is_length_truncated: Callable[[Any], bool],
    ) -> TurnResult:
        """Execute autonomous steps for a given user prompt."""
        raise NotImplementedError
