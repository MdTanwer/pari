"""Unit tests for pari.search file globbing and substring grep."""

import time
from pathlib import Path

from pari.intelligence.search import find_files, grep_search


def test_find_files(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('main')")
    (tmp_path / "src" / "helper.ts").write_text("export const x = 1;")
    (tmp_path / "README.md").write_text("# Test")

    py_files = find_files(tmp_path, pattern="*.py")
    assert "src/main.py" in py_files
    assert "README.md" not in py_files


def test_grep_search(tmp_path: Path):
    (tmp_path / "app.py").write_text("def authenticate_user():\n    return True\n")
    (tmp_path / "util.py").write_text("# No matches here\n")

    matches = grep_search(tmp_path, query="authenticate_user")
    assert len(matches) == 1
    assert matches[0]["file"] == "app.py"
    assert matches[0]["line"] == 1
    assert "def authenticate_user" in matches[0]["content"]


def test_grep_skips_an_ignored_huge_directory(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("blobs/\n")
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    (blobs / "note.txt").write_text("needle\n")
    with (blobs / "blob.bin").open("wb") as handle:
        handle.truncate(500 * 1024 * 1024)
    (tmp_path / "app.py").write_text("needle\n")

    started = time.perf_counter()
    matches = grep_search(tmp_path, query="needle")
    elapsed = time.perf_counter() - started

    assert matches == [{"file": "app.py", "line": 1, "content": "needle"}]
    assert "blobs/note.txt" not in find_files(tmp_path)
    assert elapsed < 1


def test_grep_skips_files_larger_than_one_megabyte(tmp_path: Path):
    big = tmp_path / "big.txt"
    big.write_bytes(b"needle\n")
    with big.open("ab") as handle:
        handle.truncate(1024 * 1024 + 1)
    (tmp_path / "small.txt").write_text("noise\nneedle\n")

    matches = grep_search(tmp_path, query="needle")
    assert matches == [{"file": "small.txt", "line": 2, "content": "needle"}]


def test_grep_skips_binary_files(tmp_path: Path):
    (tmp_path / "blob.bin").write_bytes(b"\0needle\n")
    (tmp_path / "app.py").write_text("needle\n")
    matches = grep_search(tmp_path, query="needle")
    assert [item["file"] for item in matches] == ["app.py"]


def test_grep_keeps_a_negated_gitignore_file(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("*.log\n!keep.log\n")
    (tmp_path / "drop.log").write_text("needle\n")
    (tmp_path / "keep.log").write_text("needle\n")
    matches = grep_search(tmp_path, query="needle")
    assert [item["file"] for item in matches] == ["keep.log"]


def test_grep_anchors_a_rooted_gitignore_pattern(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("/secret.txt\n")
    (tmp_path / "secret.txt").write_text("needle\n")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "secret.txt").write_text("needle\n")
    matches = grep_search(tmp_path, query="needle")
    assert [item["file"] for item in matches] == ["nested/secret.txt"]


def test_grep_honors_a_nested_gitignore(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / ".gitignore").write_text("secret.py\n")
    (src / "secret.py").write_text("needle\n")
    (src / "app.py").write_text("needle\n")
    matches = grep_search(tmp_path, query="needle")
    assert [item["file"] for item in matches] == ["src/app.py"]


def test_grep_still_skips_node_modules(tmp_path: Path):
    modules = tmp_path / "node_modules"
    modules.mkdir()
    (modules / "lib.js").write_text("needle\n")
    (tmp_path / "app.js").write_text("needle\n")
    matches = grep_search(tmp_path, query="needle")
    assert [item["file"] for item in matches] == ["app.js"]
