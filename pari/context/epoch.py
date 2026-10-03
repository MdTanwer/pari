"""PARI Layer 2: Immutable Context Epoch Baseline Manager.

Architectural Purpose:
    Harvested from OpenCode context-epoch.ts.
    Freezes Tiers 1-4 (System Prompt, Tools, Static Repo Map, Project Rules)
    into an immutable baseline for the duration of the epoch.
    Mid-session file edits or dynamic user turns NEVER invalidate upstream cache
    prefixes, preventing the catastrophic KV-cache invalidation cascades seen in Claude Code.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from pari.context.chunks import ContextChunk, ContextTier


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
        self.is_frozen = True

    def get_baseline_chunks(self) -> List[ContextChunk]:
        return [
            ContextChunk(
                tier=ContextTier.SYSTEM_PROMPT,
                content=self.system_prompt,
                identifier="sys_baseline",
            ),
            ContextChunk(
                tier=ContextTier.TOOL_DEFINITIONS,
                content=self.tools_schema,
                identifier="tools_baseline",
            ),
            ContextChunk(
                tier=ContextTier.STATIC_REPO_MAP,
                content=self.static_repo_map,
                identifier="repomap_baseline",
                cache_control=True,  # Primary cache breakpoint
            ),
            ContextChunk(
                tier=ContextTier.PROJECT_RULES,
                content=self.project_rules,
                identifier="rules_baseline",
            ),
        ]
