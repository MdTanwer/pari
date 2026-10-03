"""Unit tests for Layer 2 Context and Cache Architecture."""

from pari.context.chunks import ContextChunk, ContextTier, assemble_context
from pari.context.cache import mark_cache_breakpoints
from pari.context.compaction import compact_context


def test_context_assembly_and_cache_breakpoints():
    chunks = [
        ContextChunk(tier=ContextTier.SYSTEM_PROMPT, content="system instructions", identifier="sys"),
        ContextChunk(tier=ContextTier.STATIC_REPO_MAP, content="repo symbols", identifier="repo"),
        ContextChunk(tier=ContextTier.ACTIVE_FILES, content="active file code", identifier="files"),
        ContextChunk(tier=ContextTier.CURRENT_TURN, content="user query", identifier="turn"),
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
        ContextChunk(tier=ContextTier.SYSTEM_PROMPT, content="rules" * 100, identifier="sys"),
        ContextChunk(tier=ContextTier.TURN_HISTORY, content="history line" * 200, identifier="h1"),
        ContextChunk(tier=ContextTier.CURRENT_TURN, content="new turn", identifier="cur"),
    ]

    compacted = compact_context(chunks, max_tokens=100, compaction_threshold=0.5)
    # History should be replaced by a summary
    tiers = [c.tier for c in compacted]
    assert ContextTier.SYSTEM_PROMPT in tiers
    assert ContextTier.CURRENT_TURN in tiers
