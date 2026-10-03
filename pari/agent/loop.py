"""PARI Layer 4: Double-While Execution Loop.

Architectural Purpose:
    Outer loop: Session conversation interaction (waiting for user input).
    Inner loop: Autonomous tool-calling turns until task is resolved or user feedback needed.
    Continuation Guard: If the model's stop_reason == "length" (e.g. output truncated),
    automatically prompts a continuation message rather than executing broken partial syntax.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


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
        turn_count = 0
        total_tool_calls = 0

        current_prompt = prompt
        last_response = ""

        while turn_count < self.max_autonomous_turns:
            turn_count += 1
            response = await step_fn(current_prompt, turn_count)

            # Check if model output was truncated mid-stream by token limit
            if is_length_truncated(response):
                current_prompt = "Your previous output was truncated by token length limits. Please continue where you left off."
                continue

            # Process response and determine if more turns needed
            has_tool_calls = getattr(response, "has_tool_calls", False)
            if not has_tool_calls:
                last_response = getattr(response, "text", str(response))
                break

            total_tool_calls += getattr(response, "tool_call_count", 1)
            current_prompt = getattr(response, "tool_results_prompt", "")

        return TurnResult(
            response_text=last_response,
            tool_calls_executed=total_tool_calls,
            tokens_used=0,
            requires_user_input=True,
        )
