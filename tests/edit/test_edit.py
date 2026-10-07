"""Unit tests for pari.edit exact search/replace and ambiguity handling."""

import pytest

from pari.edit import (
    AmbiguousMatchError,
    PatternNotFoundError,
    apply_exact_edit,
    generate_unified_diff,
    preview_edit,
)


def test_apply_exact_edit_success():
    orig = "def auth():\n    return False\n"
    search = "    return False\n"
    replace = "    return True\n"

    res = apply_exact_edit(orig, search, replace)
    assert res == "def auth():\n    return True\n"


def test_apply_exact_edit_not_found():
    orig = "def auth():\n    return False\n"
    with pytest.raises(PatternNotFoundError):
        apply_exact_edit(orig, "non_existent_code", "replacement")


def test_apply_exact_edit_ambiguous_rejected():
    # More than one match is rejected so the edit cannot land on the wrong site.
    orig = "x = 1\nx = 1\n"
    with pytest.raises(AmbiguousMatchError) as exc_info:
        apply_exact_edit(orig, "x = 1\n", "x = 2\n", filename="test.py")

    assert exc_info.value.count == 2
    message = "Ambiguous search target in 'test.py': found 2 identical matches"
    assert message in str(exc_info.value)


def test_generate_unified_diff():
    orig = "line 1\nline 2\nline 3\n"
    mod = "line 1\nline 2 edited\nline 3\n"

    diff = generate_unified_diff(orig, mod, filename="test.py")
    assert "--- a/test.py" in diff
    assert "+++ b/test.py" in diff
    assert "-line 2" in diff
    assert "+line 2 edited" in diff


def test_preview_edit():
    orig = "alpha\nbeta\n"
    mod, diff = preview_edit(orig, "beta\n", "gamma\n", filename="test.txt")
    assert mod == "alpha\ngamma\n"
    assert "+gamma" in diff
