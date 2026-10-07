"""PARI Layer 5: Edit Engine (Multi-Tier Fuzzy Search/Replace Cascade).

Architectural Purpose:
    Harvested from Aider's search_replace.py.
    Provides robust, resilient code editing across 4 tiers:
    Tier 1: Exact string match with Stop-on-Ambiguity invariant (0 or >1 matches error).
    Tier 2: Git OSR (one-sided merge / 3-way context match).
    Tier 3: Diff-Match-Patch (DMP with strict 0.8 similarity threshold).
    Tier 4: Prefill continuation for large code generation.

Subsystems:
    - exact: Exact string search and replace with ambiguity guards
    - cascade: Multi-tier cascade orchestrator
    - git_osr: Git cherry-pick / context alignment fallback
    - dmp: Diff-Match-Patch fuzzy search fallback
    - indenter: Relative indentation normalization
    - diff: Unified diff generation
"""

from pari.edit.diff import generate_unified_diff
from pari.edit.exact import (
    AmbiguousMatchError,
    PatternNotFoundError,
    apply_exact_edit,
    preview_edit,
)


__all__ = [
    "AmbiguousMatchError",
    "PatternNotFoundError",
    "apply_exact_edit",
    "generate_unified_diff",
    "preview_edit",
]
