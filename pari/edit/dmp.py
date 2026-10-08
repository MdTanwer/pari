"""PARI Layer 5: Diff-Match-Patch (DMP) Fuzzy Search Fallback.

Architectural Purpose:
    Uses approximate string matching when exact match and line-based Git OSR fail.
    Strict Invariant:
    Threshold is capped at 0.8 minimum similarity. If best match similarity is < 0.8,
    the edit is rejected to prevent silent code corruption.
"""

from difflib import SequenceMatcher

from pari.edit.indenter import align_replacement


def apply_dmp_fuzzy(
    original: str, search: str, replace: str, threshold: float = 0.8
) -> str | None:
    """Replace one window only when it is the unique match above the threshold."""
    source = original.splitlines()
    needle = search.splitlines()
    if not needle or not source or len(needle) > len(source):
        return None
    if not any(line.strip() for line in needle):
        return None
    search_text = "\n".join(needle)
    width = len(needle)
    best = -1.0
    starts: list[int] = []
    for start in range(len(source) - width + 1):
        chunk = "\n".join(source[start : start + width])
        ratio = SequenceMatcher(a=search_text, b=chunk, autojunk=False).ratio()
        if ratio > best:
            best = ratio
            starts = [start]
        elif ratio == best:
            starts.append(start)
    if best < threshold or len(starts) != 1:
        return None
    start = starts[0]
    window = "\n".join(source[start : start + width])
    replacement = align_replacement(window, search, replace).splitlines()
    merged = source[:start] + replacement + source[start + width :]
    text = "\n".join(merged)
    if original.endswith("\n"):
        text += "\n"
    return text
