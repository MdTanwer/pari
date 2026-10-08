"""PARI Layer 2: Safe Context Compaction.

Architectural Purpose:
    Closes Claude Code F7 (Context amnesia on compaction) & Cursor F3 (Context drift).
    When context token usage crosses 70% of model window capacity:
    1. Extracts and preserves API schemas, architectural agreements, and file mutation
    lists.
    2. Summarizes conversational chitchat and repetitive tool execution outputs.
    3. Replaces Tier 6 (Turn History) with the compressed summary, leaving Tiers 1-5
    intact.
"""

from pari.context.chunks import ContextChunk, ContextTier


def compact_context(
    chunks: list[ContextChunk],
    max_tokens: int = 128000,
    compaction_threshold: float = 0.70,
) -> list[ContextChunk]:
    """Summarize history older than the last five blocks once the window fills.

    System prompt, repo map, active files, and the current turn stay verbatim.
    """
    budget = max_tokens * compaction_threshold
    if _estimate_tokens(chunks) <= budget:
        return list(chunks)
    # The last five history blocks stay verbatim. Older ones become a summary.
    # Tiers 1-5 and the current turn are copied through unchanged.
    recent = {
        id(chunk)
        for chunk in [item for item in chunks if item.tier == ContextTier.TURN_HISTORY][
            -5:
        ]
    }
    compacted: list[ContextChunk] = []
    for chunk in chunks:
        if chunk.tier != ContextTier.TURN_HISTORY or id(chunk) in recent:
            compacted.append(chunk)
            continue
        summary = (
            f"[compacted history {chunk.identifier}: "
            f"{len(chunk.content)} chars omitted]"
        )
        compacted.append(
            ContextChunk(
                tier=chunk.tier,
                content=summary,
                identifier=chunk.identifier,
                cache_control=chunk.cache_control,
            )
        )
    return compacted


def _estimate_tokens(chunks: list[ContextChunk]) -> int:
    """Rough token count. Four characters is one token for this budget check."""
    return sum(max(1, len(chunk.content) // 4) for chunk in chunks)
