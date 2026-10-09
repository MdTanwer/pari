"""CLI find, grep, and startup checks use the real engines."""

from pathlib import Path

import pytest

from pari.cli import main


def test_find_prints_matching_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('main')\n")
    code = main(["--workspace", str(tmp_path), "find", "*.py"])
    assert code == 0
    assert "src/main.py" in capsys.readouterr().out


def test_find_with_no_match_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = main(["--workspace", str(tmp_path), "find", "*.py"])
    assert code == 1
    assert "No files matched" in capsys.readouterr().err


def test_grep_prints_the_matching_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    (tmp_path / "app.py").write_text("def authenticate_user():\n    return True\n")
    code = main(["--workspace", str(tmp_path), "grep", "authenticate_user"])
    captured = capsys.readouterr()
    assert code == 0
    assert "app.py:1:def authenticate_user():" in captured.out


def test_grep_rejects_a_bad_regular_expression(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = main(["--workspace", str(tmp_path), "grep", "-r", "("])
    assert code == 2
    assert "Invalid regular expression" in capsys.readouterr().err


def test_missing_eval_suite_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    suite = tmp_path / "missing.json"
    code = main(["eval", "--suite", str(suite)])
    err = capsys.readouterr().err
    assert code == 1
    assert "not found" in err
    assert "placeholder" not in err


def test_present_eval_suite_is_not_pretended(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    suite = tmp_path / "suite.json"
    suite.write_text("{}\n")
    code = main(["eval", "--suite", str(suite)])
    err = capsys.readouterr().err
    assert code == 1
    assert "not available yet" in err
    assert "placeholder" not in err


def test_missing_pinned_file_stops_startup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = main(["--workspace", str(tmp_path), "--add", "missing.py", "--dry-run"])
    assert code == 1
    assert "File not found: missing.py" in capsys.readouterr().err


def test_sandbox_coming_soon_is_a_real_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = main(["--workspace", str(tmp_path), "--sandbox", "seatbelt", "--dry-run"])
    err = capsys.readouterr().err
    assert code == 1
    assert "coming soon" in err
    assert "placeholder" not in err


def test_dry_run_reports_the_offline_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.delenv("PARI_SANDBOX", raising=False)
    monkeypatch.delenv("PARI_SANDBOX_MODE", raising=False)
    code = main(["--workspace", str(tmp_path), "--dry-run"])
    captured = capsys.readouterr()
    assert "placeholder" not in captured.out
    assert "placeholder" not in captured.err
    if code == 0:
        assert "Model: pari-core" in captured.out
        assert "Sandbox: auto" in captured.out
        assert "Self-check passed." in captured.out
    else:
        assert "bubblewrap" in captured.err
