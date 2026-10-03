"""PARI Layer 5: Multi-Tier Edit Cascade Orchestrator.

Architectural Purpose:
    Sequences the edit attempts across tiers:
    Tier 1: Exact Match (Stop-on-Ambiguity)
    Tier 2: Git OSR (One-Sided-Merge / line alignment)
    Tier 3: Diff-Match-Patch (Fuzzy threshold 0.8)
    Tier 4: Prefill continuation
"""

from typing import Optional, Tuple
from pari.edit.exact import apply_exact_edit, AmbiguousMatchError, PatternNotFoundError
from pari.edit.git_osr import apply_git_osr
from pari.edit.dmp import apply_dmp_fuzzy


class EditCascade:
    """Orchestrates multi-tier edit fallbacks."""

    def __init__(self, allow_fallbacks: bool = True):
        self.allow_fallbacks = allow_fallbacks

    def apply(self, original: str, search: str, replace: str) -> Tuple[str, str]:
        """Apply edit using cascade. Returns (new_content, tier_used)."""
        # Tier 1: Exact match
        try:
            result = apply_exact_edit(original, search, replace)
            return result, "exact"
        except AmbiguousMatchError:
            # Ambiguity cannot be safely resolved by fuzzy fallbacks
            raise
        except PatternNotFoundError:
            if not self.allow_fallbacks:
                raise

        # Tier 2: Git OSR
        osr_result = apply_git_osr(original, search, replace)
        if osr_result is not None:
            return osr_result, "git_osr"

        # Tier 3: DMP Fuzzy Match
        dmp_result = apply_dmp_fuzzy(original, search, replace, threshold=0.8)
        if dmp_result is not None:
            return dmp_result, "dmp"

        raise PatternNotFoundError("Search block could not be matched across any cascade tier.")
