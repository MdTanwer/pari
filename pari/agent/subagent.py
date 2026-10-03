"""PARI Layer 4: Fiber-Based Research Subagent Pool.

Architectural Purpose:
    Closes Pi F2 (Process-per-subagent footprint: 4 subagents = 4 V8 runtimes = 800MB-1.8GB RAM).
    PARI runs subagents as lightweight Python asyncio tasks within the same process.
    Crucial Safety Invariant:
    Subagents are strictly restricted to READ-ONLY tasks (documentation reading, grep searches).
    All code mutations are strictly single-agent to prevent concurrent file conflicts.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, List, Optional


@dataclass
class SubagentTask:
    task_id: str
    description: str
    coro: Coroutine


class FiberSubagentPool:
    """Manages lightweight concurrent read-only research fibers."""

    def __init__(self, max_concurrency: int = 4):
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def run_task(self, task_id: str, coro: Coroutine) -> Any:
        async with self.semaphore:
            return await coro

    async def run_parallel_research(self, tasks: List[SubagentTask]) -> List[Any]:
        """Execute multiple read-only tasks concurrently using asyncio.gather."""
        coros = [self.run_task(t.task_id, t.coro) for t in tasks]
        return await asyncio.gather(*coros, return_exceptions=True)
