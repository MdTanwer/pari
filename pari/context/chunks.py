"""PARI Layer 2: 8-Tier Context Chunk Hierarchy.

Defines the structured tiers of context injected into the model:
    Tier 1: System prompt & behavioral guardrails
    Tier 2: Tool definition schemas
    Tier 3: Static codebase repository map (AST / symbols)
    Tier 4: Project rules (.pari/rules or README instructions)
    Tier 5: Active loaded files
    Tier 6: Prior conversation turns
    Tier 7: Current user turn
    Tier 8: Ephemeral scratchpad
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class ContextTier(IntEnum):
    SYSTEM_PROMPT = 1
    TOOL_DEFINITIONS = 2
    STATIC_REPO_MAP = 3
    PROJECT_RULES = 4
    ACTIVE_FILES = 5
    TURN_HISTORY = 6
    CURRENT_TURN = 7
    SCRATCHPAD = 8


@dataclass
class ContextChunk:
    tier: ContextTier
    content: str
    identifier: str
    cache_control: bool = False


def assemble_context(chunks: list[ContextChunk]) -> list[dict[str, Any]]:
    """Sort chunks by tier and format them for the model payload.

    Lower tier numbers are the stable prefix. The loop appends the current
    turn last so a cache breakpoint above it can stay warm.
    """
    ordered = sorted(chunks, key=lambda chunk: int(chunk.tier))
    return [
        {
            "id": chunk.identifier,
            "tier": int(chunk.tier),
            "content": chunk.content,
            "cache_control": chunk.cache_control,
        }
        for chunk in ordered
    ]
