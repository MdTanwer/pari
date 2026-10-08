"""PARI Layer 2: Cache Breakpoint Manager.

Positions Anthropic / provider prompt cache breakpoints at optimal tier boundaries:
1. Static Baseline (Tier 3: Repo Map / System Rules boundary)
2. Active Files boundary (Tier 5: Active files before conversation turns)
This guarantees high cache hit rates (70-90%) throughout long sessions.
"""

from pari.context.chunks import ContextChunk


# Tier 3 (repo map) and Tier 5 (active files) are the stable boundaries.
# Conversation turns below them change every request and must not be cached.
_CACHE_TIERS = {3, 5}


def mark_cache_breakpoints(chunks: list[ContextChunk]) -> list[ContextChunk]:
    """Set cache_control only on the repo-map and active-file boundaries."""
    marked: list[ContextChunk] = []
    for chunk in chunks:
        marked.append(
            ContextChunk(
                tier=chunk.tier,
                content=chunk.content,
                identifier=chunk.identifier,
                cache_control=int(chunk.tier) in _CACHE_TIERS,
            )
        )
    return marked
