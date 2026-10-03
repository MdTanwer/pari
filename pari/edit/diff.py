"""PARI Layer 5: Unified Diff Generation.

Formats edits into standard unified diffs for terminal preview and inspection.
"""

import difflib
from typing import List


def generate_unified_diff(original: str, modified: str, filename: str = "target") -> str:
    """Generate a clean unified diff between original and modified text."""
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    return "".join(diff)
