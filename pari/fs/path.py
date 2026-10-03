"""PARI Layer 6: Safe Canonical Path Resolution.

Architectural Purpose:
    Prevents path traversal attacks (e.g. ../../etc/shadow) and path prefix collisions
    (e.g., /workspace_evil matching /workspace in string-prefix checks).
    Enforces that resolved canonical paths reside strictly within authorized workspace roots.
"""

from pathlib import Path
from typing import Union


def resolve_safe_path(workspace_root: Union[str, Path], target_path: Union[str, Path]) -> Path:
    """Resolve a target path safely relative to the workspace root.
    
    Args:
        workspace_root: The authorized boundary directory.
        target_path: The relative or absolute path requested by tool/user.
        
    Returns:
        The fully resolved canonical Path object.
        
    Raises:
        PermissionError: If the resolved path lies outside workspace_root.
    """
    root = Path(workspace_root).resolve()
    target = Path(target_path)

    if target.is_absolute():
        resolved_target = target.resolve()
    else:
        resolved_target = (root / target).resolve()

    try:
        resolved_target.relative_to(root)
    except ValueError:
        raise PermissionError(
            f"Path traversal rejected: '{target_path}' resolves to '{resolved_target}', "
            f"which escapes workspace boundary '{root}'."
        )

    return resolved_target
