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
from typing import Any, Dict, List, Optional


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


def assemble_context(chunks: List[ContextChunk]) -> List[Dict[str, Any]]:
    """Sort chunks by strict tier hierarchy and format for model payload."""
    sorted_chunks = sorted(chunks, key=lambda c: c.tier)
    messages = []
    for chunk in sorted_chunks:
        entry = {
            "tier": chunk.tier.name,
            "id": chunk.identifier,
            "content": chunk.content,
        }
        if chunk.cache_control:
            entry["cache_control"] = {"type": "ephemeral"}
        messages.append(entry)
    return messages
