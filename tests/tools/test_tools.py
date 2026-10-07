"""Unit tests for Standard Tool Suite."""

from pathlib import Path

import pytest

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


@pytest.mark.asyncio
async def test_bash_tool_sandboxed(tmp_path: Path):
    registry = get_default_registry(tmp_path)
    res = await registry.execute("bash", {"command": "echo 'running bash tool'"})
    assert res["exit_code"] == 0
    assert "running bash tool" in res["output"]
