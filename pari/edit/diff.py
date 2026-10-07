"""PARI Layer 5: Unified Diff Generation.

Formats edits into standard unified diffs for terminal preview and inspection.
"""

import difflib


def generate_unified_diff(
    original: str, modified: str, filename: str = "target"
) -> str:
    """Generate a clean unified diff between original and modified text."""
    lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    return "".join(lines)
