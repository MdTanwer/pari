"""PARI Layer 3: Substring & Globbing Search Engine (v1 Baseline Navigation).

Architectural Purpose:
    Provides fast, deterministic code search without requiring C-extension compilation.
    Enforces ignore boundaries (.git, .venv, node_modules, build artifacts, and
    .gitignore) and does not read files larger than 1 MB.
"""

import os
import re
from collections.abc import Iterator
from pathlib import Path

from pari.intelligence.ignore import IgnoreRules


MAX_TEXT_BYTES = 1024 * 1024
_BINARY_PROBE = 1024


def find_files(
    workspace_root: Path, pattern: str = "*", max_results: int = 100
) -> list[str]:
    """Find files in workspace matching a glob pattern, respecting ignore rules."""
    root = workspace_root.resolve()
    matches: list[str] = []
    for path in walk_files(root):
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
    for path in walk_files(root):
        relative = path.relative_to(root).as_posix()
        if not _matches(relative, path_filter):
            continue
        for line_number, line in _iter_lines(path):
            hit = pattern.search(line) if pattern is not None else query in line
            if not hit:
                continue
            matches.append({"file": relative, "line": line_number, "content": line})
            if len(matches) >= max_matches:
                return matches
    return matches


def walk_files(workspace_root: Path) -> Iterator[Path]:
    """Yield workspace files that ignore rules do not hide."""
    root = workspace_root.resolve()
    rules = IgnoreRules(root)
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        rules.enter(current)
        kept: list[str] = []
        for name in sorted(dirnames):
            if not rules.ignored(current / name, is_dir=True):
                kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            path = current / name
            if rules.ignored(path, is_dir=False):
                continue
            yield path


def is_binary(path: Path) -> bool:
    """A NUL in the first 1 KB marks a binary file."""
    try:
        with path.open("rb") as handle:
            return b"\0" in handle.read(_BINARY_PROBE)
    except OSError:
        return True


def _matches(relative: str, pattern: str) -> bool:
    path = Path(relative)
    if "/" not in pattern and "**" not in pattern:
        return path.match(pattern) or Path(path.name).match(pattern)
    return path.match(pattern)


def _iter_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Stream text lines. Skip binaries and files over 1 MB."""
    try:
        if path.stat().st_size > MAX_TEXT_BYTES:
            return
        handle = path.open("rb")
    except OSError:
        return
    with handle:
        if b"\0" in handle.read(_BINARY_PROBE):
            return
        handle.seek(0)
        for number, raw in enumerate(handle, start=1):
            text = raw.decode("utf-8", errors="replace")
            if text.endswith("\n"):
                text = text[:-1]
            if text.endswith("\r"):
                text = text[:-1]
            yield number, text
