"""PARI Layer 5: Git One-Sided Merge (OSR) Fallback.

Architectural Purpose:
    Harvested from Aider's git cherry-pick / 3-way merge strategy.
    When an exact match fails due to minor surrounding line drift, Git OSR treats
    the search block as a base revision and attempts a 3-way context alignment.
"""

from typing import Optional


def apply_git_osr(original: str, search: str, replace: str) -> Optional[str]:
    """Attempt 3-way context alignment using line-based diff matching."""
    # Simplified line-anchored context matching
    orig_lines = original.splitlines()
    search_lines = search.splitlines()
    replace_lines = replace.splitlines()

    if not search_lines:
        return None

    # Try finding the best line sequence match
    first_search_line = search_lines[0].strip()
    candidate_indices = [
        i for i, line in enumerate(orig_lines)
        if line.strip() == first_search_line
    ]

    for idx in candidate_indices:
        # Check if subsequent lines match with high similarity
        matches = 0
        window = orig_lines[idx:idx + len(search_lines)]
        for s_line, o_line in zip(search_lines, window):
            if s_line.strip() == o_line.strip():
                matches += 1

        if matches >= max(1, int(len(search_lines) * 0.8)):
            # Replace candidate window
            new_lines = orig_lines[:idx] + replace_lines + orig_lines[idx + len(search_lines):]
            return "\n".join(new_lines)

    return None
