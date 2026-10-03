"""Fast codebase navigation: substring/regex grep and path globbing."""

import os
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class GrepMatch:
    file_path: str
    line_number: int
    line_content: str

    def __getitem__(self, item: str):
        if item == "file":
            return self.file_path
        if item == "line":
            return self.line_number
        if item == "content":
            return self.line_content
        raise KeyError(item)


IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".pari", "dist", "build"
}


def find_files(workspace_root: Path, pattern: str = "*", max_results: int = 100) -> List[str]:
    """Find files in workspace matching a glob pattern, respecting ignore rules."""
    results: List[str] = []
    workspace_root = workspace_root.resolve()

    for root, dirs, files in os.walk(workspace_root):
        # Prune ignored directories in-place
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        rel_root = Path(root).relative_to(workspace_root)
        for f in files:
            if f.startswith("."):
                continue
            rel_path = str(rel_root / f) if str(rel_root) != "." else f
            
            # Simple fnmatch check
            import fnmatch
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(f, pattern):
                results.append(rel_path)
                if len(results) >= max_results:
                    return results

    return results


def grep_search(
    workspace_root: Path,
    query: str,
    is_regex: bool = False,
    path_filter: str = "*",
    max_matches: int = 50
) -> List[Dict]:
    """Search for query across files in workspace, returning matches with line numbers."""
    matches: List[Dict] = []
    workspace_root = workspace_root.resolve()
    
    pattern = re.compile(query) if is_regex else re.compile(re.escape(query))

    candidate_files = find_files(workspace_root, pattern=path_filter, max_results=500)

    for rel_path in candidate_files:
        full_path = workspace_root / rel_path
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, start=1):
                    if pattern.search(line):
                        matches.append(GrepMatch(
                            file_path=rel_path,
                            line_number=line_num,
                            line_content=line.rstrip("\r\n"),
                        ))
                        if len(matches) >= max_matches:
                            return matches
        except (OSError, UnicodeDecodeError):
            continue

    return matches

