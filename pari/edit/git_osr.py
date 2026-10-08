"""PARI Layer 5: Git One-Sided Merge (OSR) Fallback.

Architectural Purpose:
    Harvested from Aider's git cherry-pick / 3-way merge strategy.
    When an exact match fails due to minor surrounding line drift, Git OSR treats
    the search block as a base revision and attempts a 3-way context alignment.
"""

from pari.edit.indenter import align_replacement


def apply_git_osr(original: str, search: str, replace: str) -> str | None:
    """Replace the one window whose stripped lines equal the search block.

    A snippet is not a full-file revision, so a synthetic cherry-pick cannot
    see where it belongs. Unique stripped-line alignment is the same decision
    the merge would make, and a second hit is left untouched.
    """
    source = original.splitlines()
    needle = search.splitlines()
    if not needle or len(needle) > len(source):
        return None
    if not any(line.strip() for line in needle):
        return None
    wanted = [line.strip() for line in needle]
    width = len(needle)
    hits = [
        start
        for start in range(len(source) - width + 1)
        if [line.strip() for line in source[start : start + width]] == wanted
    ]
    if len(hits) != 1:
        return None
    start = hits[0]
    window = "\n".join(source[start : start + width])
    replacement = align_replacement(window, search, replace).splitlines()
    merged = source[:start] + replacement + source[start + width :]
    return _with_original_ending(original, merged)


def _with_original_ending(original: str, lines: list[str]) -> str:
    text = "\n".join(lines)
    if original.endswith("\n"):
        text += "\n"
    return text
