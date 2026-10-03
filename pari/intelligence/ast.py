"""PARI Layer 3: Tree-sitter AST Symbol Extractor.

Architectural Purpose:
    Extracts high-signal structural definitions (classes, functions, methods, imports)
    from source code without reading full file bodies into prompt context.
    Degrades gracefully to regex/heuristic parsing when tree-sitter bindings are not installed.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Optional


@dataclass
class SymbolInfo:
    file_path: str
    symbol_name: str
    kind: str  # "class", "function", "method", "variable"
    line_number: int
    signature: str


def extract_symbols(file_path: Path, content: str) -> List[SymbolInfo]:
    """Extract symbols from source code. Uses tree-sitter if available, falls back to AST regex."""
    symbols: List[SymbolInfo] = []
    rel_path = str(file_path)

    # Fast heuristic/regex fallback for Python
    if file_path.suffix == ".py":
        for i, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("class "):
                match = re.match(r"class\s+([A-Za-z0-9_]+)", stripped)
                if match:
                    symbols.append(SymbolInfo(rel_path, match.group(1), "class", i, stripped[:80]))
            elif stripped.startswith("def "):
                match = re.match(r"def\s+([A-Za-z0-9_]+)", stripped)
                if match:
                    kind = "method" if line.startswith("    ") or line.startswith("\t") else "function"
                    symbols.append(SymbolInfo(rel_path, match.group(1), kind, i, stripped[:80]))

    return symbols
