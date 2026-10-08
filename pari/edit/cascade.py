"""PARI Layer 5: Multi-Tier Edit Cascade Orchestrator.

Architectural Purpose:
    Sequences the edit attempts across tiers:
    Tier 1: Exact Match (Stop-on-Ambiguity)
    Tier 2: Git OSR (One-Sided-Merge / line alignment)
    Tier 3: Diff-Match-Patch (Fuzzy threshold 0.8)
    Tier 4: Prefill continuation
"""

from difflib import SequenceMatcher

from pari.edit.dmp import apply_dmp_fuzzy
from pari.edit.exact import AmbiguousMatchError, PatternNotFoundError, apply_exact_edit
from pari.edit.git_osr import apply_git_osr


class EditCascade:
    """Try an exact edit, then whitespace alignment, then a fuzzy window."""

    def __init__(self, allow_fallbacks: bool = True):
        self.allow_fallbacks = allow_fallbacks

    def apply(
        self,
        original: str,
        search: str,
        replace: str,
        filename: str = "<unknown>",
    ) -> tuple[str, str]:
        """Return (new content, tier). Ambiguous matches always abort."""
        try:
            return apply_exact_edit(original, search, replace, filename), "exact"
        except AmbiguousMatchError:
            raise
        except PatternNotFoundError:
            if not self.allow_fallbacks:
                raise
        updated = apply_git_osr(original, search, replace)
        if updated is not None:
            return updated, "git_osr"
        updated = apply_dmp_fuzzy(original, search, replace)
        if updated is not None:
            return updated, "dmp"
        raise PatternNotFoundError(_targeted_retry(filename, original, search))


def _targeted_retry(filename: str, original: str, search: str) -> str:
    """Ask for one block again, with the nearest lines, not the whole file."""
    lines = original.splitlines()
    start = _nearest_window(lines, search.splitlines())
    body = "\n".join(lines[start : start + 15])
    return (
        f"Could not locate search block in {filename}.\n"
        "Current physical file content at target lines is:\n"
        "--------------------------------------------------\n"
        f"{body}\n"
        "--------------------------------------------------\n"
        "Emit ONLY the corrected SEARCH/REPLACE block for these lines."
    )


def _nearest_window(lines: list[str], needle: list[str]) -> int:
    if not needle or len(needle) > len(lines):
        return 0
    search_text = "\n".join(needle)
    width = len(needle)
    best = -1.0
    start = 0
    for index in range(len(lines) - width + 1):
        chunk = "\n".join(lines[index : index + width])
        ratio = SequenceMatcher(a=search_text, b=chunk, autojunk=False).ratio()
        if ratio > best:
            best = ratio
            start = index
    return start
