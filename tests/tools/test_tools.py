"""Unit tests for Standard Tool Suite."""

import asyncio
import threading
import time
from pathlib import Path

import pytest

from pari.edit.exact import PatternNotFoundError
from pari.tools.bash import MAX_TOOL_TIMEOUT, BashTool
from pari.tools.registry import get_default_registry


@pytest.mark.asyncio
async def test_tool_registry_and_fs_tools(tmp_path: Path):
    registry = get_default_registry(tmp_path)
    schemas = registry.get_schemas()
    names = [s["name"] for s in schemas]
    assert "bash" in names
    assert "read_file" in names
    assert "write_file" in names
    assert "edit_file" in names
    assert "find_files" in names
    assert "grep_search" in names
    assert "read_tool_output" in names

    # Test write_file
    res = await registry.execute(
        "write_file", {"path": "hello.txt", "content": "Hello World!"}
    )
    assert "Successfully wrote" in res

    # Test read_file
    content = await registry.execute("read_file", {"path": "hello.txt"})
    assert content == "Hello World!"

    # Test edit_file
    edit_res = await registry.execute(
        "edit_file",
        {"path": "hello.txt", "search": "World", "replace": "PARI"},
    )
    assert edit_res["status"] == "success"
    assert edit_res["tier"] == "exact"

    updated = await registry.execute("read_file", {"path": "hello.txt"})
    assert updated == "Hello PARI!"

    with pytest.raises(PermissionError):
        await registry.execute(
            "write_file", {"path": "../outside.txt", "content": "nope"}
        )


@pytest.mark.asyncio
async def test_write_file_refuses_git_and_pari(tmp_path: Path):
    registry = get_default_registry(tmp_path)
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    with pytest.raises(PermissionError, match="reserved"):
        await registry.execute(
            "write_file",
            {"path": ".git/hooks/pre-commit", "content": "#!/bin/sh\n"},
        )
    assert not hook.exists()
    assert not (tmp_path / ".git").exists()

    log = tmp_path / ".pari" / "sessions" / "log.jsonl"
    with pytest.raises(PermissionError, match="reserved"):
        await registry.execute(
            "write_file",
            {"path": ".pari/sessions/log.jsonl", "content": "tampered\n"},
        )
    assert not log.exists()
    assert not (tmp_path / ".pari").exists()


@pytest.mark.asyncio
async def test_edit_file_refuses_pari_and_git(tmp_path: Path):
    log = tmp_path / ".pari" / "session.jsonl"
    log.parent.mkdir(parents=True)
    original = '{"event":"turn"}\n'
    log.write_text(original)
    head = tmp_path / ".git" / "HEAD"
    head.parent.mkdir()
    head_text = "ref: refs/heads/main\n"
    head.write_text(head_text)
    registry = get_default_registry(tmp_path)

    with pytest.raises(PermissionError, match="reserved"):
        await registry.execute(
            "edit_file",
            {
                "path": ".pari/session.jsonl",
                "search": "turn",
                "replace": "tampered",
            },
        )
    assert log.read_text() == original

    with pytest.raises(PermissionError, match="reserved"):
        await registry.execute(
            "edit_file",
            {"path": ".git/HEAD", "search": "main", "replace": "evil"},
        )
    assert head.read_text() == head_text


@pytest.mark.asyncio
async def test_read_file_can_read_git(tmp_path: Path):
    head = tmp_path / ".git" / "HEAD"
    head.parent.mkdir()
    head.write_text("ref: refs/heads/main\n")
    registry = get_default_registry(tmp_path)
    content = await registry.execute("read_file", {"path": ".git/HEAD"})
    assert content == "ref: refs/heads/main\n"


@pytest.mark.asyncio
async def test_edit_fallback_none_refuses_indent_drift(tmp_path: Path):
    path = tmp_path / "app.py"
    original = "def greet():\n    return 'hi'\n"
    path.write_text(original)
    registry = get_default_registry(tmp_path)
    with pytest.raises(PatternNotFoundError):
        await registry.execute(
            "edit_file",
            {
                "path": "app.py",
                "search": "def greet():\n  return 'hi'\n",
                "replace": "def greet():\n  return 'hello'\n",
            },
        )
    # A refused edit must leave the file byte-for-byte unchanged.
    assert path.read_text() == original


@pytest.mark.asyncio
async def test_edit_fallback_cascade_aligns_indent(tmp_path: Path):
    path = tmp_path / "app.py"
    path.write_text("def greet():\n    return 'hi'\n")
    registry = get_default_registry(tmp_path, edit_fallback="cascade")
    result = await registry.execute(
        "edit_file",
        {
            "path": "app.py",
            "search": "def greet():\n  return 'hi'\n",
            "replace": "def greet():\n  return 'hello'\n",
        },
    )
    assert result["tier"] == "git_osr"
    assert path.read_text() == "def greet():\n    return 'hello'\n"


@pytest.mark.asyncio
async def test_read_file_bounds_a_large_file(tmp_path: Path):
    path = tmp_path / "big.log"
    line = "line\n"
    path.write_text(line * ((10 * 1024 * 1024) // len(line)))
    registry = get_default_registry(tmp_path)
    content = await registry.execute("read_file", {"path": "big.log"})
    # The returned window, notice included, stays inside the 100 KB budget.
    assert len(content.encode("utf-8")) < 100 * 1024
    assert "OMITTED" in content
    assert "tool-outputs" in content
    # The notice points at a real sidecar that holds the full file.
    sidecar = _sidecar_from_notice(content)
    assert sidecar.is_file()
    assert sidecar.stat().st_size > 1_000_000


@pytest.mark.asyncio
async def test_read_file_bounds_a_large_file_by_bytes(tmp_path: Path):
    # Long lines trip the byte cap before the 2,000-line cap.
    path = tmp_path / "wide.log"
    path.write_text(("x" * 99 + "\n") * 200_000)
    registry = get_default_registry(tmp_path)
    content = await registry.execute("read_file", {"path": "wide.log"})
    assert len(content.encode("utf-8")) < 100 * 1024
    assert "OMITTED" in content


@pytest.mark.asyncio
async def test_read_file_offset_and_limit_window(tmp_path: Path):
    path = tmp_path / "lines.txt"
    path.write_text("a\nb\nc\nd\ne\n")
    registry = get_default_registry(tmp_path)
    window = await registry.execute(
        "read_file", {"path": "lines.txt", "offset": 2, "limit": 2}
    )
    assert window == "b\nc\n"


@pytest.mark.asyncio
async def test_read_file_returns_a_binary_message(tmp_path: Path):
    path = tmp_path / "icon.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    registry = get_default_registry(tmp_path)
    content = await registry.execute("read_file", {"path": "icon.png"})
    assert content == "Binary file: icon.png"


@pytest.mark.asyncio
async def test_grep_rejects_a_bad_regular_expression(tmp_path: Path):
    registry = get_default_registry(tmp_path)
    with pytest.raises(ValueError, match="Invalid regular expression"):
        await registry.execute("grep_search", {"query": "(", "is_regex": True})


@pytest.mark.asyncio
async def test_huge_timeout_is_capped(tmp_path: Path):
    registry = get_default_registry(tmp_path)
    started = time.monotonic()
    result = await registry.execute("bash", {"command": "sleep 1000", "timeout": 99999})
    elapsed = time.monotonic() - started
    assert result["timed_out"] is True
    assert result["timeout"] == MAX_TOOL_TIMEOUT
    assert elapsed < MAX_TOOL_TIMEOUT


@pytest.mark.asyncio
async def test_string_timeout_runs(tmp_path: Path):
    registry = get_default_registry(tmp_path)
    result = await registry.execute("bash", {"command": "echo hi", "timeout": "5"})
    assert result["exit_code"] == 0
    assert "hi" in result["output"]
    assert result["timed_out"] is False


@pytest.mark.asyncio
async def test_bad_timeout_is_an_argument_error(tmp_path: Path):
    registry = get_default_registry(tmp_path)
    result = await registry.execute("bash", {"command": "echo hi", "timeout": "nope"})
    assert "timeout" in result["error"]
    assert "must be a number" in result["error"]


@pytest.mark.asyncio
async def test_string_integer_and_boolean_are_coerced(tmp_path: Path):
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("two\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("use (parens)\n", encoding="utf-8")
    registry = get_default_registry(tmp_path)
    found = await registry.execute(
        "find_files", {"pattern": "*.txt", "max_results": "1"}
    )
    assert len(found) == 1
    matches = await registry.execute("grep_search", {"query": "(", "is_regex": "false"})
    assert matches
    assert matches[0]["content"] == "use (parens)"


@pytest.mark.asyncio
async def test_bash_tool_sandboxed(tmp_path: Path):
    registry = get_default_registry(tmp_path)
    res = await registry.execute("bash", {"command": "echo 'running bash tool'"})
    assert res["exit_code"] == 0
    assert "running bash tool" in res["output"]
    assert res["timed_out"] is False

    # The workspace is the only writable mount: a write outside it must not
    # reach the host filesystem.
    escape = tmp_path.parent / "pari_escape_probe.txt"
    await registry.execute("bash", {"command": f"echo x > {escape} 2>/dev/null; true"})
    assert not escape.exists()


@pytest.mark.asyncio
async def test_small_bash_calls_create_no_sidecars(tmp_path: Path):
    registry = get_default_registry(tmp_path)
    for _ in range(100):
        result = await registry.execute("bash", {"command": "echo hi"})
        assert result["exit_code"] == 0
        assert result["sidecar_path"] == ""
    spool = tmp_path / ".pari" / "tool-outputs"
    assert list(spool.glob("*.txt")) == []


def test_ctrl_c_during_sleep_leaves_no_sleep_process(tmp_path: Path):
    tool = BashTool(tmp_path)
    thread = threading.Thread(
        target=lambda: asyncio.run(tool.execute("sleep 100", timeout=120))
    )
    thread.start()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and not _sleep_pids():
        time.sleep(0.05)
    assert _sleep_pids()
    tool.cleanup()
    thread.join(10)
    assert _sleep_pids() == []


def _sleep_pids() -> list[int]:
    found: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ")
        except OSError:
            continue
        if command.decode(errors="replace").strip() == "sleep 100":
            found.append(int(entry.name))
    return found


def _sidecar_from_notice(content: str) -> Path:
    """Pull the sidecar path out of the read_file omission notice."""
    marker = "Full file: "
    start = content.index(marker) + len(marker)
    end = content.index("]", start)
    return Path(content[start:end].strip())
