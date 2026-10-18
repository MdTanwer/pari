"""PARI Layer 6: Safe Canonical Path Resolution.

Architectural Purpose:
    Prevents path traversal attacks (e.g. ../../etc/shadow) and path prefix collisions
    (e.g., /workspace_evil matching /workspace in string-prefix checks).
    Enforces that resolved canonical paths reside strictly within authorized workspace
    roots.
"""

from pathlib import Path


# File tools run on the host. `.git/hooks` runs on the next commit, and
# `.pari` holds the session audit log. Reads of these trees stay allowed.
_WRITE_RESERVED = frozenset({".git", ".pari"})


def resolve_safe_path(workspace_root: str | Path, target_path: str | Path) -> Path:
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
        raise PermissionError(
            f"Path traversal rejected: '{target_path}' "
            f"is outside workspace '{workspace_root}'"
        )

    return resolved


def resolve_writable_path(workspace_root: str | Path, target_path: str | Path) -> Path:
    """Resolve a path the file tools may create or overwrite.

    The resolved path must stay inside the workspace. Its first component
    must not be .git or .pari, including when a symlink or ``..`` lands there.
    read_file keeps using resolve_safe_path, so a read of .git stays allowed.
    """
    resolved = resolve_safe_path(workspace_root, target_path)
    root = Path(workspace_root).resolve()
    relative = resolved.relative_to(root)
    reserved = relative.parts[0] if relative.parts else ""
    if reserved in _WRITE_RESERVED:
        raise PermissionError(
            f"Write refused: '{target_path}' is inside reserved directory '{reserved}'"
        )
    return resolved
