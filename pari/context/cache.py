"""PARI Layer 2: Cache Breakpoint Manager.

Positions prompt-cache breakpoints at the tier boundaries that stay stable:
1. Tool schemas (tier 2)
2. Repository map (tier 3)
3. Project rules (tier 4)
4. Active files (tier 5)
Turns below those boundaries are not cached.
"""

from pari.context.chunks import ContextChunk


# Breakpoints sit on the tool schema, the frozen baseline, the repo map,
# and the active files. Turns below tier 5 change every request.
_CACHE_TIERS = {2, 3, 4, 5}


def mark_cache_breakpoints(chunks: list[ContextChunk]) -> list[ContextChunk]:
    """Set cache_control on tiers 2, 3, 4, and 5. Turns stay unmarked."""
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
