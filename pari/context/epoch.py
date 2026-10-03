"""PARI Layer 2: Immutable Context Epoch Baseline Manager.

Architectural Purpose:
    Harvested from OpenCode context-epoch.ts.
    Freezes Tiers 1-4 (System Prompt, Tools, Static Repo Map, Project Rules)
    into an immutable baseline for the duration of the epoch.
    Mid-session file edits or dynamic user turns NEVER invalidate upstream cache
    prefixes, preventing the catastrophic KV-cache invalidation cascades seen in Claude Code.
"""

from dataclasses import dataclass
from typing import List
from pari.context.chunks import ContextChunk


@dataclass
class ContextEpoch:
    epoch_id: str
    version: int = 1
    system_prompt: str = ""
    tools_schema: str = ""
    static_repo_map: str = ""
    project_rules: str = ""
    is_frozen: bool = False

    def freeze(self):
        """Freeze baseline tiers to lock KV cache prefix."""
        raise NotImplementedError

    def get_baseline_chunks(self) -> List[ContextChunk]:
        """Assemble immutable baseline context chunks."""
        raise NotImplementedError
