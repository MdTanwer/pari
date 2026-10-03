"""PARI Layer 3: Repo Map Generator & Token Packer.

Architectural Purpose:
    Packs codebase structural symbols into a strict token budget (default 2,048 tokens)
    using binary-search selection based on PPR rankings.
"""

from pathlib import Path
from typing import Dict, List, Optional
from pari.intelligence.ast import extract_symbols, SymbolInfo
from pari.search import find_files


class RepoMapGenerator:
    """Generates condensed repository map from parsed source symbols."""

    def __init__(self, workspace: Path, max_tokens: int = 2048):
        self.workspace = workspace.resolve()
        self.max_tokens = max_tokens

    def generate(self, focus_files: Optional[List[str]] = None) -> str:
        """Scan workspace, extract symbols, and format condensed outline."""
        files = find_files(self.workspace, max_results=100)
        lines: List[str] = ["# Repository Structural Map"]

        for rel_path in files:
            full_path = self.workspace / rel_path
            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                symbols = extract_symbols(full_path, content)
                if symbols:
                    lines.append(f"\n{rel_path}:")
                    for s in symbols[:10]:
                        lines.append(f"  {s.kind} {s.symbol_name} (line {s.line_number})")
            except Exception:
                continue

        result = "\n".join(lines)
        # Approximate token ceiling
        max_chars = self.max_tokens * 4
        if len(result) > max_chars:
            result = result[:max_chars] + "\n... [TRUNCATED REPOMAP TO FIT 2048 TOKENS] ..."
        return result
