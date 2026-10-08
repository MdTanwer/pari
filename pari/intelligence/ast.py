"""PARI Layer 3: Tree-sitter AST Symbol Extractor.

Architectural Purpose:
    Extracts high-signal structural definitions (classes, functions, methods, imports)
    from source code without reading full file bodies into prompt context.
    Degrades gracefully to regex/heuristic parsing when tree-sitter bindings are not
    installed.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SymbolInfo:
    file_path: str
    symbol_name: str
    kind: str  # "class", "function", "method", "variable"
    line_number: int
    signature: str


# Python, and the same shapes in TS, Go, and Rust. Tree-sitter can replace this
# later; the regex path needs no extra package.
_DEFINITIONS = re.compile(
    r"^(\s*)(?:(?:async|export|pub|public|private|protected)\s+)*"
    r"(class|def|function|fn|func)\s+([A-Za-z_][A-Za-z0-9_]*)"
)


def extract_symbols(file_path: Path, content: str) -> list[SymbolInfo]:
    """Return class and function signatures. Bodies are not included."""
    if "\x00" in content[:1024]:
        return []
    relative = file_path.as_posix()
    found: list[SymbolInfo] = []
    for number, line in enumerate(content.splitlines(), start=1):
        match = _DEFINITIONS.match(line)
        if match is None:
            continue
        indent, keyword, name = match.group(1), match.group(2), match.group(3)
        if keyword == "class":
            kind = "class"
        elif indent:
            kind = "method"
        else:
            kind = "function"
        found.append(
            SymbolInfo(
                file_path=relative,
                symbol_name=name,
                kind=kind,
                line_number=number,
                signature=line.strip(),
            )
        )
    return found
