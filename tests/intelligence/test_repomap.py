"""Repo map ranking, symbol extraction, and the worktree cache."""

from pathlib import Path

from pari.intelligence.ast import extract_symbols
from pari.intelligence.cache import WorktreeSymbolCache
from pari.intelligence.ppr import compute_personalized_pagerank
from pari.intelligence.repomap import RepoMapGenerator


def test_extract_symbols_reads_signatures_only():
    content = "class Auth:\n    def verify(self):\n        return 1\n"
    symbols = extract_symbols(Path("auth.py"), content)
    assert [item.symbol_name for item in symbols] == ["Auth", "verify"]
    assert symbols[0].kind == "class"
    assert symbols[1].kind == "method"
    assert "return 1" not in symbols[1].signature


def test_hub_ranks_below_the_named_symbol():
    edges = [(f"file{index}.py", "utils") for index in range(60)]
    edges.append(("app.py", "AuthService"))
    ranks = compute_personalized_pagerank(edges, {"AuthService"})
    assert ranks["AuthService"] > ranks["utils"]


def test_cache_is_scoped_to_the_workspace(tmp_path: Path):
    one = tmp_path / "one"
    two = tmp_path / "two"
    one.mkdir()
    two.mkdir()
    first = WorktreeSymbolCache(one)
    second = WorktreeSymbolCache(two)
    assert first.get_db_path() != second.get_db_path()
    first.put_symbols("auth.py", 1.0, [{"file_path": "auth.py", "symbol_name": "Auth"}])
    assert first.get_symbols("auth.py", 1.0) is not None
    assert first.get_symbols("auth.py", 2.0) is None
    assert second.get_symbols("auth.py", 1.0) is None


def test_repo_map_prefers_the_focused_file(tmp_path: Path):
    (tmp_path / "other.py").write_text("def other():\n    return 0\n")
    (tmp_path / "auth.py").write_text("def verify_jwt():\n    return 1\n")
    text = RepoMapGenerator(tmp_path, max_tokens=8).generate(["auth.py"])
    assert "verify_jwt" in text
    assert "other" not in text


def test_repo_map_skips_ignored_lockfiles_and_huge_files(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("skip/\n")
    skipped = tmp_path / "skip"
    skipped.mkdir()
    (skipped / "secret.py").write_text("def hidden_secret():\n    return 1\n")
    (tmp_path / "package-lock.json").write_text("def lock_symbol():\n    return 1\n")
    (tmp_path / "blob.bin").write_bytes(b"\0def binary_symbol():\n")
    huge = tmp_path / "huge.py"
    huge.write_text("def huge_symbol():\n    return 1\n")
    with huge.open("ab") as handle:
        handle.truncate(1024 * 1024 + 1)
    (tmp_path / "auth.py").write_text("def verify_jwt():\n    return 1\n")

    text = RepoMapGenerator(tmp_path, max_tokens=2048).generate()
    assert "verify_jwt" in text
    assert "hidden_secret" not in text
    assert "lock_symbol" not in text
    assert "binary_symbol" not in text
    assert "huge_symbol" not in text
