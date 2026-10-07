"""PARI Layer 2: Cache Breakpoint Manager.

Positions Anthropic / provider prompt cache breakpoints at optimal tier boundaries:
1. Static Baseline (Tier 3: Repo Map / System Rules boundary)
2. Active Files boundary (Tier 5: Active files before conversation turns)
This guarantees high cache hit rates (70-90%) throughout long sessions.
"""

from pari.context.chunks import ContextChunk


def mark_cache_breakpoints(chunks: list[ContextChunk]) -> list[ContextChunk]:
    """Inspect chunks and ensure cache_control flags are set only on key tier
    boundaries."""
    raise NotImplementedError
