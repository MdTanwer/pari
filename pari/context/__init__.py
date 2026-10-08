"""PARI Layer 2: Context and Cache Architecture.

Architectural Purpose:
    Closes Claude Code F4 (KV cache invalidation cascades causing 10x billing spikes)
    and Claude Code F7 / Cursor F3 (Context amnesia & drift on compaction).

Subsystems:
    - epoch: Immutable Context Epoch baseline manager
    - chunks: 8-tier context chunk hierarchy assembly
    - cache: Strategic cache breakpoint positioning for prompt caching
    - compaction: Schema-preserving context compaction at 70% threshold
    - warmer: Background economic cache warmer maintaining prompt cache state
"""

from pari.context.cache import mark_cache_breakpoints
from pari.context.chunks import ContextChunk, ContextTier, assemble_context
from pari.context.compaction import compact_context
from pari.context.epoch import ContextEpoch
from pari.context.warmer import CacheWarmer, expected_savings, should_warm


__all__ = [
    "CacheWarmer",
    "ContextChunk",
    "ContextEpoch",
    "ContextTier",
    "assemble_context",
    "compact_context",
    "expected_savings",
    "mark_cache_breakpoints",
    "should_warm",
]
