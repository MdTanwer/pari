"""PARI Layer 3: Substring & Globbing Search Engine (v1 Baseline Navigation).

Architectural Purpose:
    Provides fast, deterministic code search without requiring C-extension compilation.
    Enforces ignore boundaries (.git, .venv, node_modules, build artifacts).
"""

import os
import re
from pathlib import Path


_IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".pari",
}


def find_files(
    workspace_root: Path, pattern: str = "*", max_results: int = 100
) -> list[str]:
    """Find files in workspace matching a glob pattern, respecting ignore rules."""
    root = workspace_root.resolve()
    matches: list[str] = []
    for path in _walk_files(root):
        relative = path.relative_to(root).as_posix()
        if not _matches(relative, pattern):
            continue
        matches.append(relative)
        if len(matches) >= max_results:
            break
    return matches


def grep_search(
    workspace_root: Path,
    query: str,
    is_regex: bool = False,
    path_filter: str = "*",
    max_matches: int = 50,
) -> list[dict[str, str | int]]:
    """Search for query across files in workspace, returning matches with line
    numbers."""
    pattern = re.compile(query) if is_regex else None
    matches: list[dict[str, str | int]] = []
    root = workspace_root.resolve()
    for relative in find_files(root, path_filter, max_results=10**9):
        text = _read_text(root / relative)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            hit = pattern.search(line) if pattern is not None else query in line
            if not hit:
                continue
            matches.append({"file": relative, "line": line_number, "content": line})
            if len(matches) >= max_matches:
                return matches
    return matches


def _walk_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in _IGNORED_DIRS)
        for name in sorted(filenames):
            yield Path(dirpath) / name


def _matches(relative: str, pattern: str) -> bool:
    path = Path(relative)
    if "/" not in pattern and "**" not in pattern:
        return path.match(pattern) or Path(path.name).match(pattern)
    return path.match(pattern)


def _read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:1024]:
        return None
    return data.decode("utf-8", errors="replace")
