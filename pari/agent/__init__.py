"""PARI Layer 4: The Execution Loop (Agent Runtime).

Architectural Purpose:
    Implements the double-while execution loop with stop_reason == "length"
    truncation guard and bounded reflection retry limits.

Subsystems:
    - loop: Core double-while agent loop with continuation handling
    - runtime: Turn execution, tool orchestration, and state transitions
    - reflection: Structured error injection with max 3 reflection retries
"""

from pari.agent.guards import (
    DAEMON_IDLE_SECONDS,
    LENGTH_TRUNCATION_NOTICE,
    MAX_TURNS,
    TURN_WARNING,
    format_daemon_notice,
    is_length_stop,
)
from pari.agent.loop import AgentExecutionLoop, TurnResult
from pari.agent.reflection import ReflectionManager, format_lint_error
from pari.agent.runtime import AgentRuntime


__all__ = [
    "DAEMON_IDLE_SECONDS",
    "LENGTH_TRUNCATION_NOTICE",
    "MAX_TURNS",
    "TURN_WARNING",
    "AgentExecutionLoop",
    "AgentRuntime",
    "ReflectionManager",
    "TurnResult",
    "format_daemon_notice",
    "format_lint_error",
    "is_length_stop",
]
