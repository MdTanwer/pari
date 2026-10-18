"""Unit tests for Layer 7 Output Handling & Context Hygiene."""

import asyncio
import os
from pathlib import Path

import pytest

from pari.output.parser import parse_test_failures
from pari.output.spooler import ManagedOutputSpooler
from pari.output.truncation import extract_head_tail
from pari.tools.output_reader import ReadToolOutputTool


def test_head_tail_truncation():
    long_output = "\n".join(f"line {i}" for i in range(500))
    condensed, truncated = extract_head_tail(
        long_output, head_lines=10, tail_lines=20, sidecar_path="/tmp/out.log"
    )
    assert truncated is True
    assert "line 0" in condensed
    assert "line 499" in condensed
    assert "OMITTED" in condensed


def test_small_output_does_not_write_a_sidecar(tmp_path: Path):
    spool_dir = tmp_path / "spool"
    spooler = ManagedOutputSpooler(spool_dir=spool_dir)
    res = spooler.spool("hi", command_tag="bash")
    assert res.was_truncated is False
    assert res.context_text == "hi"
    assert res.sidecar_path is None
    assert list(spool_dir.glob("*.txt")) == []


def test_managed_output_spooler(tmp_path: Path):
    spooler = ManagedOutputSpooler(spool_dir=tmp_path / "spool", max_bytes=200)
    huge_text = "error dump\n" * 50
    res = spooler.spool(huge_text, command_tag="pytest")
    assert res.was_truncated is True
    assert res.sidecar_path.exists()
    assert res.sidecar_path.read_text() == huge_text


def test_spooler_drops_sidecars_older_than_seven_days(tmp_path: Path):
    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()
    stale = spool_dir / "old.txt"
    stale.write_text("gone")
    fresh = spool_dir / "new.txt"
    fresh.write_text("keep")
    week = 7 * 24 * 60 * 60
    stale_time = stale.stat().st_mtime - week - 5
    os.utime(stale, (stale_time, stale_time))

    spooler = ManagedOutputSpooler(spool_dir=spool_dir)
    assert not stale.exists()
    assert fresh.read_text() == "keep"
    later = spool_dir / "later.txt"
    later.write_text("old")
    later_time = later.stat().st_mtime - week - 5
    os.utime(later, (later_time, later_time))
    assert spooler.purge_expired() == 1
    assert not later.exists()


def test_read_tool_output_rejects_paths_outside_the_spool(tmp_path: Path):
    spool_dir = tmp_path / "tool-outputs"
    spool_dir.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("hidden")
    tool = ReadToolOutputTool(spool_dir)
    with pytest.raises(PermissionError):
        asyncio.run(tool.execute(str(secret)))


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
