"""PARI Layer 3: Tree-sitter AST Symbol Extractor.

Architectural Purpose:
    Extracts high-signal structural definitions (classes, functions, methods, imports)
    from source code without reading full file bodies into prompt context.
    Degrades gracefully to regex/heuristic parsing when tree-sitter bindings are not installed.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class SymbolInfo:
    file_path: str
    symbol_name: str
    kind: str  # "class", "function", "method", "variable"
    line_number: int
    signature: str


def extract_symbols(file_path: Path, content: str) -> List[SymbolInfo]:
    """Extract symbols from source code."""
    raise NotImplementedError
