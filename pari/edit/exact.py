"""PARI Layer 5: Exact String Search & Replace with Ambiguity Guard.

Architectural Invariant:
    Stop-on-Ambiguity:
    - If search pattern occurs 0 times: Raise PatternNotFoundError.
    - If search pattern occurs > 1 times: Raise AmbiguousMatchError.
    - An edit is ONLY applied if the search pattern matches EXACTLY once.
"""

from typing import Tuple
from pari.edit.diff import generate_unified_diff


class PatternNotFoundError(Exception):
    """Raised when the search string does not exist in target content."""
    pass


class AmbiguousMatchError(Exception):
    """Raised when the search string occurs multiple times in target content."""
    def __init__(self, count: int, search_str: str, filename: str = "<unknown>"):
        super().__init__(
            f"Ambiguous search target in '{filename}': found {count} identical matches. "
            "Please provide additional surrounding context to identify a unique block."
        )
        self.count = count
        self.search_str = search_str
        self.filename = filename


def apply_exact_edit(original: str, search: str, replace: str, filename: str = "<unknown>") -> str:
    """Applies search/replace to text, strictly requiring a single unique match.
    
    Args:
        original: Full file content.
        search: Target block to replace.
        replace: Replacement block.
        filename: Optional filename for error reporting.
        
    Returns:
        Updated content.
    """
    count = original.count(search)
    if count == 0:
        raise PatternNotFoundError(f"Search block not found in target file '{filename}'.")
    if count > 1:
        raise AmbiguousMatchError(count, search, filename=filename)

    return original.replace(search, replace, 1)


def preview_edit(original: str, search: str, replace: str, filename: str = "<unknown>") -> Tuple[str, str]:
    """Applies exact edit and returns both modified content and unified diff."""
    modified = apply_exact_edit(original, search, replace, filename=filename)
    diff = generate_unified_diff(original, modified, filename=filename)
    return modified, diff
