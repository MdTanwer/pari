"""PARI Layer 4: Fiber-Based Research Subagent Pool.

Architectural Purpose:
    Closes Pi F2 (Process-per-subagent footprint: 4 subagents = 4 V8 runtimes =
    800MB-1.8GB RAM).
    PARI runs subagents as lightweight Python asyncio tasks within the same process.
    Crucial Safety Invariant:
    Subagents are strictly restricted to READ-ONLY tasks (documentation reading, grep
    searches).
    All code mutations are strictly single-agent to prevent concurrent file conflicts.
"""

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any


@dataclass
class SubagentTask:
    task_id: str
    description: str
    coro: Coroutine


class FiberSubagentPool:
    """Runs read-only research tasks as coroutines in this process.

    The pool does not check the coroutine body. The loop must only hand it
    read tools (grep, find, read_file, read_tool_output). A write belongs
    on the parent agent, which holds the file locks.
    """

    def __init__(self, max_concurrency: int = 4):
        self.max_concurrency = max_concurrency
        self._slots = asyncio.Semaphore(max_concurrency)

    async def run_task(self, _task_id: str, coro: Coroutine) -> Any:
        """Run one research task, waiting if the pool is already full."""
        async with self._slots:
            return await coro

    async def run_parallel_research(self, tasks: list[SubagentTask]) -> list[Any]:
        """Run the tasks together and return results in input order.

        Cancelling the parent task cancels the group, so a stopped turn does
        not leave research coroutines running.
        """
        results: list[Any] = [None] * len(tasks)

        async def _store(index: int, task: SubagentTask) -> None:
            results[index] = await self.run_task(task.task_id, task.coro)

        async with asyncio.TaskGroup() as group:
            for index, task in enumerate(tasks):
                group.create_task(_store(index, task))
        return results
