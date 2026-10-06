"""PARI Layer 6: Safe Canonical Path Resolution.

Architectural Purpose:
    Prevents path traversal attacks (e.g. ../../etc/shadow) and path prefix collisions
    (e.g., /workspace_evil matching /workspace in string-prefix checks).
    Enforces that resolved canonical paths reside strictly within authorized workspace roots.
"""

from pathlib import Path
from typing import Union


def resolve_safe_path(workspace_root: Union[str, Path], target_path: Union[str, Path]) -> Path:
    """Resolve a target path safely relative to the workspace root."""
    root = Path(workspace_root).resolve()
    target = Path(target_path)
    if not target.is_absolute():
        resolved = (root / target).resolve()
    else:
        resolved = target.resolve()

    try:
        resolved.relative_to(root)
    except ValueError:
        raise PermissionError(f"Path traversal rejected: '{target_path}' is outside workspace '{workspace_root}'")

    return resolved

