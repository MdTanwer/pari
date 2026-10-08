"""Unit tests for Layer 2 Context and Cache Architecture."""

import asyncio

import pytest

from pari.context.cache import mark_cache_breakpoints
from pari.context.chunks import ContextChunk, ContextTier, assemble_context
from pari.context.compaction import compact_context
from pari.context.epoch import ContextEpoch
from pari.context.warmer import CacheWarmer, should_warm


def test_context_assembly_and_cache_breakpoints():
    chunks = [
        ContextChunk(
            tier=ContextTier.SYSTEM_PROMPT,
            content="system instructions",
            identifier="sys",
        ),
        ContextChunk(
            tier=ContextTier.STATIC_REPO_MAP,
            content="repo symbols",
            identifier="repo",
        ),
        ContextChunk(
            tier=ContextTier.ACTIVE_FILES,
            content="active file code",
            identifier="files",
        ),
        ContextChunk(
            tier=ContextTier.CURRENT_TURN, content="user query", identifier="turn"
        ),
    ]

    marked = mark_cache_breakpoints(chunks)
    # Tier 3 (Repo Map) and Tier 5 (Active files) should have cache_control=True
    assert marked[1].cache_control is True
    assert marked[2].cache_control is True
    assert marked[3].cache_control is False

    assembled = assemble_context(marked)
    assert len(assembled) == 4
    assert assembled[0]["id"] == "sys"


def test_context_compaction_preserves_boundaries():
    chunks = [
        ContextChunk(
            tier=ContextTier.SYSTEM_PROMPT, content="rules" * 100, identifier="sys"
        ),
        ContextChunk(
            tier=ContextTier.TURN_HISTORY,
            content="history line" * 200,
            identifier="h1",
        ),
        ContextChunk(
            tier=ContextTier.CURRENT_TURN, content="new turn", identifier="cur"
        ),
    ]

    compacted = compact_context(chunks, max_tokens=100, compaction_threshold=0.5)
    # History should be replaced by a summary
    tiers = [c.tier for c in compacted]
    assert ContextTier.SYSTEM_PROMPT in tiers
    assert ContextTier.CURRENT_TURN in tiers


def test_epoch_freeze_keeps_the_prefix():
    epoch = ContextEpoch(epoch_id="e1", system_prompt="be careful", tools_schema="bash")
    first = epoch.get_baseline_chunks()
    epoch.system_prompt = "changed later"
    second = epoch.get_baseline_chunks()
    assert epoch.is_frozen is True
    assert first[0].content == "be careful"
    assert second[0].content == "be careful"
    assert [chunk.tier for chunk in first] == [
        ContextTier.SYSTEM_PROMPT,
        ContextTier.TOOL_DEFINITIONS,
    ]


def test_compaction_keeps_the_last_five_history_blocks():
    chunks = [
        ContextChunk(ContextTier.SYSTEM_PROMPT, "rules", "sys"),
    ]
    for index in range(6):
        chunks.append(ContextChunk(ContextTier.TURN_HISTORY, "x" * 400, f"h{index}"))
    chunks.append(ContextChunk(ContextTier.CURRENT_TURN, "now", "cur"))
    compacted = compact_context(chunks, max_tokens=100, compaction_threshold=0.5)
    history = [chunk for chunk in compacted if chunk.tier == ContextTier.TURN_HISTORY]
    assert history[0].content.startswith("[compacted history")
    assert all(not item.content.startswith("[compacted") for item in history[1:])
    assert len(history) == 6


def test_warmer_pings_only_when_the_savings_clear_the_floor():
    assert should_warm(80_000) is False
    assert should_warm(300_000) is True


@pytest.mark.asyncio
async def test_warmer_skips_a_small_context():
    calls: list[str] = []

    async def ping() -> None:
        calls.append("ping")

    warmer = CacheWarmer(interval_seconds=0.01, warm_callback=ping, context_tokens=100)
    warmer.start()
    await asyncio.sleep(0.05)
    await warmer.stop()
    assert calls == []


@pytest.mark.asyncio
async def test_warmer_pings_a_large_context():
    calls: list[str] = []

    def ping() -> None:
        calls.append("ping")

    warmer = CacheWarmer(
        interval_seconds=0.01, warm_callback=ping, context_tokens=300_000
    )
    warmer.start()
    await asyncio.sleep(0.05)
    await warmer.stop()
    assert calls
