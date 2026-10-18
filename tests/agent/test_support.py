"""Helpers the hand-written execution loop calls."""

import asyncio

import pytest

from pari.agent.guards import (
    LENGTH_TRUNCATION_NOTICE,
    MAX_TURNS,
    format_daemon_notice,
    is_length_stop,
)
from pari.agent.reflection import ReflectionManager, format_lint_error
from pari.agent.subagent import FiberSubagentPool, SubagentTask


def test_length_stop_discards_a_cut_off_tool_call():
    assert is_length_stop("length") is True
    assert is_length_stop("end_turn") is False
    assert "No changes were written to disk" in LENGTH_TRUNCATION_NOTICE
    assert MAX_TURNS == 40


def test_reflection_stops_after_three_failures():
    manager = ReflectionManager()
    assert manager.should_retry("edit-1") is True
    first = manager.record_failure("edit-1", "LINT ERROR", "line 4")
    assert "attempt 1/3" in first
    manager.record_failure("edit-1", "LINT ERROR", "line 4")
    last = manager.record_failure("edit-1", "LINT ERROR", "line 4")
    assert manager.should_retry("edit-1") is False
    assert "Reflection limit reached" in last
    manager.reset("edit-1")
    assert manager.should_retry("edit-1") is True


def test_lint_block_names_the_enclosing_function():
    block = format_lint_error(
        "src/auth.py",
        42,
        "def parse_bearer_token(header: str) -> str:",
        "42:     return header.split(' ')[1]",
    )
    assert "[LINT ERROR] In src/auth.py:42:" in block
    assert "parse_bearer_token" in block


def test_daemon_notice_names_the_command():
    notice = format_daemon_notice("npm run dev")
    assert "npm run dev" in notice
    assert "was stopped after 10s" in notice
    assert "separate terminal" in notice
    assert "background" not in notice


@pytest.mark.asyncio
async def test_subagent_pool_returns_results_in_order():
    pool = FiberSubagentPool(max_concurrency=2)

    async def work(value: int) -> int:
        await asyncio.sleep(0.01)
        return value

    tasks = [SubagentTask(str(value), "read", work(value)) for value in (1, 2, 3)]
    assert await pool.run_parallel_research(tasks) == [1, 2, 3]
