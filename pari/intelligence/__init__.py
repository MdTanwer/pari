"""PARI Layer 3: Codebase Intelligence & Navigation Layer.

Architectural Purpose:
    Closes Pi F3 (Blind file traversal loops requiring 8+ grep turns) and
    Aider F4 (Personalized PageRank hub distortion from generic utility sinks).

Subsystems:
    - search: Fast file globbing & ripgrep substring search (v1 primary navigation)
    - ast: Tree-sitter AST symbol extractor across Python, TypeScript, Go, Rust
    - ppr: Personalized PageRank graph ranking with hub suppression (>50 inbound refs
    dampened)
    - repomap: 2,048-token binary-search packing for the static context repo map
    - cache: Worktree-scoped SQLite symbol cache preventing lock collisions
"""

from pari.intelligence.ast import SymbolInfo, extract_symbols
from pari.intelligence.cache import WorktreeSymbolCache
from pari.intelligence.ppr import compute_personalized_pagerank
from pari.intelligence.repomap import RepoMapGenerator
from pari.intelligence.search import find_files, grep_search


__all__ = [
    "RepoMapGenerator",
    "SymbolInfo",
    "WorktreeSymbolCache",
    "compute_personalized_pagerank",
    "extract_symbols",
    "find_files",
    "grep_search",
]
