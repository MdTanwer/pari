"""PARI Layer 3: Repo Map Generator & Token Packer.

Architectural Purpose:
    Packs codebase structural symbols into a strict token budget (default 2,048 tokens)
    using binary-search selection based on PPR rankings.
"""

from pathlib import Path

from pari.intelligence.ast import SymbolInfo, extract_symbols
from pari.intelligence.cache import WorktreeSymbolCache
from pari.intelligence.ppr import compute_personalized_pagerank
from pari.intelligence.search import MAX_TEXT_BYTES, is_binary, walk_files


class RepoMapGenerator:
    """Rank symbols and keep the prefix that fits in the token budget."""

    def __init__(self, workspace: Path, max_tokens: int = 2048):
        self.workspace = workspace.resolve()
        self.max_tokens = max_tokens
        self.cache = WorktreeSymbolCache(self.workspace)

    def generate(self, focus_files: list[str] | None = None) -> str:
        """Scan the workspace and return the ranked signature map."""
        symbols = self._symbols()
        if not symbols:
            return ""
        edges = [(item.file_path, item.symbol_name) for item in symbols]
        targets = set(focus_files or [])
        targets.update(
            item.symbol_name for item in symbols if item.file_path in targets
        )
        ranks = compute_personalized_pagerank(edges, targets)
        ordered = sorted(
            symbols,
            key=lambda item: ranks.get(item.symbol_name, 0.0),
            reverse=True,
        )
        return _pack(ordered, self.max_tokens)

    def _symbols(self) -> list[SymbolInfo]:
        found: list[SymbolInfo] = []
        for path in _source_files(self.workspace):
            relative = path.relative_to(self.workspace).as_posix()
            mtime = path.stat().st_mtime
            cached = self.cache.get_symbols(relative, mtime)
            if cached is not None:
                found.extend(_from_cache(cached))
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            extracted = extract_symbols(Path(relative), content)
            self.cache.put_symbols(
                relative, mtime, [_as_dict(item) for item in extracted]
            )
            found.extend(extracted)
        return found


def _pack(symbols: list[SymbolInfo], max_tokens: int) -> str:
    """Keep the highest-ranked signatures until the next one would overflow."""
    blocks: list[str] = []
    used = 0
    current_file = ""
    for symbol in symbols:
        header = ""
        if symbol.file_path != current_file:
            header = f"# {symbol.file_path}\n"
        line = f"{header}{symbol.signature}"
        cost = max(1, len(line) // 4)
        if blocks and used + cost > max_tokens:
            break
        blocks.append(line)
        used += cost
        current_file = symbol.file_path
    return "\n".join(blocks)


_LOCKFILES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "cargo.lock",
        "poetry.lock",
        "gemfile.lock",
        "composer.lock",
        "bun.lock",
        "pipfile.lock",
    }
)


def _source_files(workspace: Path) -> list[Path]:
    found: list[Path] = []
    for path in walk_files(workspace):
        if path.name.casefold() in _LOCKFILES:
            continue
        try:
            if path.stat().st_size > MAX_TEXT_BYTES:
                continue
        except OSError:
            continue
        if is_binary(path):
            continue
        found.append(path)
    return found


def _as_dict(symbol: SymbolInfo) -> dict[str, str | int]:
    return {
        "file_path": symbol.file_path,
        "symbol_name": symbol.symbol_name,
        "kind": symbol.kind,
        "line_number": symbol.line_number,
        "signature": symbol.signature,
    }


def _from_cache(rows: list[dict]) -> list[SymbolInfo]:
    restored: list[SymbolInfo] = []
    for row in rows:
        restored.append(
            SymbolInfo(
                file_path=str(row["file_path"]),
                symbol_name=str(row["symbol_name"]),
                kind=str(row["kind"]),
                line_number=int(row["line_number"]),
                signature=str(row["signature"]),
            )
        )
    return restored
