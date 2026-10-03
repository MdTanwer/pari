"""PARI Layer 4: The Execution Loop (Agent Runtime).

Architectural Purpose:
    Implements the double-while execution loop with stop_reason == "length" truncation guard,
    bounded reflection retry limits, and lightweight asyncio fiber-based subagents.

Subsystems:
    - loop: Core double-while agent loop with continuation handling
    - runtime: Turn execution, tool orchestration, and state transitions
    - reflection: Structured error injection with max 3 reflection retries
    - subagent: Fiber-based read-only research subagents (closing Pi F2 RAM bloat)
"""

from pari.agent.loop import AgentExecutionLoop
from pari.agent.runtime import AgentRuntime
from pari.agent.reflection import ReflectionManager
from pari.agent.subagent import FiberSubagentPool

__all__ = [
    "AgentExecutionLoop",
    "AgentRuntime",
    "ReflectionManager",
    "FiberSubagentPool",
]
