"""PARI Layer 3: Substring & Globbing Search Engine (v1 Baseline Navigation).

Architectural Purpose:
    Provides fast, deterministic code search without requiring C-extension compilation.
    Enforces ignore boundaries (.git, .venv, node_modules, build artifacts).
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class GrepMatch:
    file_path: str
    line_number: int
    line_content: str


def find_files(
    workspace_root: Path, pattern: str = "*", max_results: int = 100
) -> list[str]:
    """Find files in workspace matching a glob pattern, respecting ignore rules."""
    raise NotImplementedError


def grep_search(
    workspace_root: Path,
    query: str,
    is_regex: bool = False,
    path_filter: str = "*",
    max_matches: int = 50,
) -> list[GrepMatch]:
    """Search for query across files in workspace, returning matches with line
    numbers."""
    raise NotImplementedError
