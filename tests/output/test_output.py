"""Unit tests for Layer 7 Output Handling & Context Hygiene."""

from pathlib import Path
from pari.output.spooler import ManagedOutputSpooler
from pari.output.truncation import extract_head_tail
from pari.output.parser import parse_test_failures


def test_head_tail_truncation():
    long_output = "\n".join(f"line {i}" for i in range(500))
    condensed, truncated = extract_head_tail(long_output, head_lines=10, tail_lines=20, sidecar_path="/tmp/out.log")
    assert truncated is True
    assert "line 0" in condensed
    assert "line 499" in condensed
    assert "OMITTED" in condensed


def test_managed_output_spooler(tmp_path: Path):
    spooler = ManagedOutputSpooler(spool_dir=tmp_path / "spool", max_bytes=200)
    huge_text = "error dump\n" * 50
    res = spooler.spool(huge_text, command_tag="pytest")
    assert res.was_truncated is True
    assert res.sidecar_path.exists()
    assert res.sidecar_path.read_text() == huge_text


def test_parse_test_failures():
    raw = """
=== FAILURES ===
________________________________ test_something ________________________________
def test_something():
>   assert 1 == 2
E   AssertionError: assert 1 == 2
FAILED tests/test_something.py::test_something - AssertionError: assert 1 == 2
"""
    fails = parse_test_failures(raw)
    assert len(fails) >= 1
    assert any("FAILED" in f for f in fails)
