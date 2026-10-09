"""Unit tests for Standard Tool Suite."""

from pathlib import Path

import pytest

from pari.edit.exact import PatternNotFoundError
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

    updated = await registry.execute("read_file", {"path": "hello.txt"})
    assert updated == "Hello PARI!"

    with pytest.raises(PermissionError):
        await registry.execute(
            "write_file", {"path": "../outside.txt", "content": "nope"}
        )


@pytest.mark.asyncio
async def test_edit_fallback_none_refuses_indent_drift(tmp_path: Path):
    path = tmp_path / "app.py"
    path.write_text("def greet():\n    return 'hi'\n")
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
    assert "return 'hi'" in path.read_text()


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
    assert path.read_text().startswith("def greet():\n    return 'hello'\n")


@pytest.mark.asyncio
async def test_grep_rejects_a_bad_regular_expression(tmp_path: Path):
    registry = get_default_registry(tmp_path)
    with pytest.raises(ValueError, match="Invalid regular expression"):
        await registry.execute("grep_search", {"query": "(", "is_regex": True})


@pytest.mark.asyncio
async def test_bash_tool_sandboxed(tmp_path: Path):
    registry = get_default_registry(tmp_path)
    res = await registry.execute("bash", {"command": "echo 'running bash tool'"})
    assert res["exit_code"] == 0
    assert "running bash tool" in res["output"]
