"""PARI Layer 4: The Execution Loop (Agent Runtime).

Architectural Purpose:
    Implements the double-while execution loop with stop_reason == "length" truncation
    guard,
    bounded reflection retry limits, and lightweight asyncio fiber-based subagents.

Subsystems:
    - loop: Core double-while agent loop with continuation handling
    - runtime: Turn execution, tool orchestration, and state transitions
    - reflection: Structured error injection with max 3 reflection retries
    - subagent: Fiber-based read-only research subagents (closing Pi F2 RAM bloat)
"""

# Placeholder imports will be exported once implementations are added
