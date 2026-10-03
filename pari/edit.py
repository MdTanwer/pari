"""Exact search-and-replace edit engine with strict fail-safe ambiguity handling."""

import difflib
from typing import Tuple


class EditError(Exception):
    """Base exception for edit failures."""
    pass


class PatternNotFoundError(EditError):
    """Raised when the search block cannot be located in the target content."""
    pass


class AmbiguousMatchError(EditError):
    """Raised when the search block matches more than one location in the file."""
    def __init__(self, count: int, filename: str = ""):
        self.count = count
        self.filename = filename
        super().__init__(
            f"Ambiguous search target in '{filename}': found {count} identical matches. "
            "Edit rejected to prevent applying changes to the wrong location. "
            "Please provide additional surrounding context lines to uniquely identify the target."
        )


def apply_exact_edit(original_text: str, search_block: str, replace_block: str, filename: str = "") -> str:
    """Apply an exact search-and-replace edit.
    
    Guarantees:
        - Fails closed if search_block is missing.
        - Fails closed if search_block matches more than once (Stop on Ambiguity).
        - Replaces strictly the single unambiguous match.
    """
    if not search_block:
        raise PatternNotFoundError("Search block cannot be empty.")

    match_count = original_text.count(search_block)
    
    if match_count == 0:
        raise PatternNotFoundError(
            f"Search block not found in '{filename}'. Content has drifted or lines do not match."
        )
    elif match_count > 1:
        raise AmbiguousMatchError(match_count, filename=filename)

    # Exactly one match confirmed
    return original_text.replace(search_block, replace_block, 1)


def generate_unified_diff(original_text: str, modified_text: str, filename: str = "file") -> str:
    """Generate a clean unified diff string."""
    orig_lines = original_text.splitlines(keepends=True)
    mod_lines = modified_text.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=3,
    )
    return "".join(diff)


def preview_edit(original_text: str, search_block: str, replace_block: str, filename: str = "file") -> Tuple[str, str]:
    """Test and preview an edit, returning (modified_text, diff)."""
    modified = apply_exact_edit(original_text, search_block, replace_block, filename=filename)
    diff = generate_unified_diff(original_text, modified, filename=filename)
    return modified, diff
