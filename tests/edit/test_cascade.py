"""Cascade fallbacks leave an ambiguous or weak edit untouched."""

import pytest

from pari.edit import (
    AmbiguousMatchError,
    EditCascade,
    PatternNotFoundError,
    normalize_relative_indentation,
)


def test_exact_match_stays_on_the_first_tier():
    original = "def auth():\n    return False\n"
    updated, tier = EditCascade().apply(
        original, "    return False\n", "    return True\n"
    )
    assert tier == "exact"
    assert updated == "def auth():\n    return True\n"


def test_ambiguous_match_does_not_fall_through():
    original = "x = 1\nx = 1\n"
    with pytest.raises(AmbiguousMatchError):
        EditCascade().apply(original, "x = 1\n", "x = 2\n")


def test_indent_drift_uses_line_alignment():
    original = "def greet():\n    return 'hi'\n\ndef other():\n    return 1\n"
    search = "def greet():\n  return 'hi'\n"
    replace = "def greet():\n  return 'hello'\n"
    updated, tier = EditCascade().apply(original, search, replace, "app.py")
    assert tier == "git_osr"
    assert "return 'hello'" in updated
    assert "return 1" in updated
    assert updated.startswith("def greet():\n    return 'hello'\n")


def test_small_typo_uses_the_fuzzy_window():
    original = "def greet():\n    return 'hi'\n"
    search = "def greet():\n    return 'hii'\n"
    replace = "def greet():\n    return 'hello'\n"
    updated, tier = EditCascade().apply(original, search, replace)
    assert tier == "dmp"
    assert updated == "def greet():\n    return 'hello'\n"


def test_unrelated_block_asks_for_a_narrow_retry():
    original = "def other():\n    return 1\n"
    with pytest.raises(PatternNotFoundError, match="Could not locate") as exc:
        EditCascade().apply(original, "totally missing block", "x = 1\n", "app.py")
    assert "def other():" in str(exc.value)
    assert "Emit ONLY the corrected SEARCH/REPLACE" in str(exc.value)


def test_disabled_fallbacks_keep_the_exact_error():
    original = "def other():\n    return 1\n"
    with pytest.raises(PatternNotFoundError, match="not found"):
        EditCascade(allow_fallbacks=False).apply(original, "missing", "x = 1\n")


def test_relative_indent_shifts_the_replacement():
    search = "    def foo():\n        return 1\n"
    replace = "  def foo():\n      return 2\n"
    assert normalize_relative_indentation(search, replace) == (
        "    def foo():\n        return 2\n"
    )
