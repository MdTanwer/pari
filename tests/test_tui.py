"""Unit tests for Layer 9 Interactive Terminal Application & REPL."""

from pathlib import Path
from pari.tui.app import TerminalApp


def test_tui_process_message_greeting(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    
    # Test variations of "hi how are you" / "hi howr you"
    assert app.process_message("hi how are you") == "Good! How can I help you today?"
    assert app.process_message("hi howr you") == "Good! How can I help you today?"
    assert app.process_message("how r you") == "Good! How can I help you today?"
    assert app.process_message("Hi How Are You?") == "Good! How can I help you today?"


def test_tui_process_message_help(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    res = app.process_message("/help")
    assert "/help" in res
    assert "/exit" in res


def test_tui_slash_commands(tmp_path: Path):
    app = TerminalApp(workspace=tmp_path)
    
    # /diff command
    diff_res = app.process_message("/diff")
    assert "diff" in diff_res.lower()
    
    # /model command
    model_res = app.process_message("/model")
    assert "pari-core" in model_res
    
    switch_res = app.process_message("/model gpt-4o")
    assert "gpt-4o" in switch_res
    assert app.model_name == "gpt-4o"
    
    # /undo command
    undo_res = app.process_message("/undo")
    assert "undo" in undo_res.lower()
    
    # /add command with existing file
    test_file = tmp_path / "hello.py"
    test_file.write_text("print('test')")
    add_res = app.process_message(f"/add {test_file.name}")
    assert "Added" in add_res or "Pinned" in add_res




def test_cost_meter():
    from pari.tui.status import CostMeter
    meter = CostMeter(model_family="pari-core")
    meter.add_usage(in_tokens=1000, out_tokens=500)
    assert meter.usage.total_tokens == 1500
    assert meter.calculate_cost_usd() > 0
    status = meter.format_status()
    assert "1.5k tokens" in status
    assert "$" in status

