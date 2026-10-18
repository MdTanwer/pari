"""Paths for session logs and DAGs in the user's system directory."""

import hashlib
import os
from pathlib import Path


def default_session_dir(workspace: Path | None = None) -> Path:
    """Return the system directory for session logs, outside the project root."""
    raw = os.environ.get("PARI_SESSION_DIR")
    if raw:
        return Path(raw)
    base = Path.home() / ".pari"
    if workspace is not None:
        clean = workspace.resolve()
        digest = hashlib.sha256(str(clean).encode("utf-8")).hexdigest()[:8]
        slug = f"{clean.name}-{digest}"
        return base / "projects" / slug / "sessions"
    return base / "sessions"
