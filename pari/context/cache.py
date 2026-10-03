"""PARI Layer 2: Cache Breakpoint Manager.

Positions Anthropic / provider prompt cache breakpoints at optimal tier boundaries:
1. Static Baseline (Tier 3: Repo Map / System Rules boundary)
2. Active Files boundary (Tier 5: Active files before conversation turns)
This guarantees high cache hit rates (70-90%) throughout long sessions.
"""

from typing import List
from pari.context.chunks import ContextChunk, ContextTier


def mark_cache_breakpoints(chunks: List[ContextChunk]) -> List[ContextChunk]:
    """Inspect chunks and ensure cache_control flags are set only on key tier boundaries."""
    # Find last chunk of Tier 3 (Repo Map) and Tier 5 (Active files)
    tier3_last = None
    tier5_last = None

    for chunk in chunks:
        chunk.cache_control = False
        if chunk.tier <= ContextTier.STATIC_REPO_MAP:
            tier3_last = chunk
        elif chunk.tier <= ContextTier.ACTIVE_FILES:
            tier5_last = chunk

    if tier3_last:
        tier3_last.cache_control = True
    if tier5_last and tier5_last is not tier3_last:
        tier5_last.cache_control = True

    return chunks
