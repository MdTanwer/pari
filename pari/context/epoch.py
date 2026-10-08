"""PARI Layer 2: Immutable Context Epoch Baseline Manager.

Architectural Purpose:
    Harvested from OpenCode context-epoch.ts.
    Freezes Tiers 1-4 (System Prompt, Tools, Static Repo Map, Project Rules)
    into an immutable baseline for the duration of the epoch.
    Mid-session file edits or dynamic user turns NEVER invalidate upstream cache
    prefixes, preventing the catastrophic KV-cache invalidation cascades seen in Claude
    Code.
"""

from dataclasses import dataclass, field

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
    _baseline: tuple[str, str, str, str] | None = field(default=None, repr=False)

    def freeze(self) -> None:
        """Copy tiers 1-4. Later edits to those fields stay out of the prefix."""
        if self.is_frozen:
            return
        self._baseline = (
            self.system_prompt,
            self.tools_schema,
            self.static_repo_map,
            self.project_rules,
        )
        self.is_frozen = True

    def get_baseline_chunks(self) -> list[ContextChunk]:
        """Return the frozen tiers 1-4. The first call freezes them."""
        if not self.is_frozen:
            self.freeze()
        assert self._baseline is not None
        system, tools, repo, rules = self._baseline
        pieces = (
            (ContextTier.SYSTEM_PROMPT, system, "system"),
            (ContextTier.TOOL_DEFINITIONS, tools, "tools"),
            (ContextTier.STATIC_REPO_MAP, repo, "repomap"),
            (ContextTier.PROJECT_RULES, rules, "rules"),
        )
        return [
            ContextChunk(tier=tier, content=content, identifier=name)
            for tier, content, name in pieces
            if content
        ]
