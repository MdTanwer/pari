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

from pari.edit.cascade import EditCascade
from pari.edit.diff import generate_unified_diff
from pari.edit.dmp import apply_dmp_fuzzy
from pari.edit.exact import (
    AmbiguousMatchError,
    PatternNotFoundError,
    apply_exact_edit,
    preview_edit,
)
from pari.edit.git_osr import apply_git_osr
from pari.edit.indenter import normalize_relative_indentation


__all__ = [
    "AmbiguousMatchError",
    "EditCascade",
    "PatternNotFoundError",
    "apply_dmp_fuzzy",
    "apply_exact_edit",
    "apply_git_osr",
    "generate_unified_diff",
    "normalize_relative_indentation",
    "preview_edit",
]
