"""PARI Layer 5: Diff-Match-Patch (DMP) Fuzzy Search Fallback.

Architectural Purpose:
    Uses approximate string matching when exact match and line-based Git OSR fail.
    Strict Invariant:
    Threshold is capped at 0.8 minimum similarity. If best match similarity is < 0.8,
    the edit is rejected to prevent silent code corruption.
"""

import difflib
from typing import Optional


def apply_dmp_fuzzy(original: str, search: str, replace: str, threshold: float = 0.8) -> Optional[str]:
    """Find the best fuzzy match for search block and apply replacement if above threshold."""
    search_len = len(search)
    if search_len == 0 or len(original) < search_len:
        return None

    # Sliding window fuzzy match
    best_ratio = 0.0
    best_start = -1

    # Check chunks near candidate locations
    step = max(1, search_len // 4)
    for i in range(0, len(original) - search_len + 1, step):
        chunk = original[i:i + search_len]
        ratio = difflib.SequenceMatcher(None, search, chunk).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_start = i

    if best_ratio >= threshold and best_start != -1:
        return original[:best_start] + replace + original[best_start + search_len:]

    return None
