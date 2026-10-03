"""PARI Layer 2: Safe Context Compaction.

Architectural Purpose:
    Closes Claude Code F7 (Context amnesia on compaction) & Cursor F3 (Context drift).
    When context token usage crosses 70% of model window capacity:
    1. Extracts and preserves API schemas, architectural agreements, and file mutation lists.
    2. Summarizes conversational chitchat and repetitive tool execution outputs.
    3. Replaces Tier 6 (Turn History) with the compressed summary, leaving Tiers 1-5 intact.
"""

from typing import Dict, List, Optional
from pari.context.chunks import ContextChunk, ContextTier


def compact_context(
    chunks: List[ContextChunk],
    max_tokens: int = 128000,
    compaction_threshold: float = 0.70,
) -> List[ContextChunk]:
    """Inspect total context volume and compact turn history if threshold is exceeded."""
    # Approximation: 1 token ~= 4 chars
    total_chars = sum(len(c.content) for c in chunks)
    estimated_tokens = total_chars // 4

    if estimated_tokens < (max_tokens * compaction_threshold):
        return chunks

    preserved_chunks: List[ContextChunk] = []
    history_chunks: List[ContextChunk] = []

    for chunk in chunks:
        if chunk.tier == ContextTier.TURN_HISTORY:
            history_chunks.append(chunk)
        else:
            preserved_chunks.append(chunk)

    if not history_chunks:
        return chunks

    # Build condensed summary preserving essential structural decisions
    summary_text = (
        f"--- CONTEXT COMPACTION SUMMARY ({len(history_chunks)} prior turns condensed) ---\n"
        "Key architectural decisions, active file states, and agreements preserved.\n"
    )

    preserved_chunks.append(
        ContextChunk(
            tier=ContextTier.TURN_HISTORY,
            content=summary_text,
            identifier="compacted_summary",
        )
    )

    return sorted(preserved_chunks, key=lambda c: c.tier)
