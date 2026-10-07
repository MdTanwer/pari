"""Unit tests for pari.search file globbing and substring grep."""

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
