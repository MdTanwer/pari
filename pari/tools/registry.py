"""PARI Tools: Central Registry and Dispatcher.

Manages tool registration, schema exportation for model prompts, and dispatch execution.
"""

from pathlib import Path
from typing import Any

from pari.fs.queue import FileMutationQueue
from pari.output.spooler import ManagedOutputSpooler
from pari.tools.base import Tool
from pari.tools.bash import BashTool
from pari.tools.fs import EditFileTool, ReadFileTool, WriteFileTool
from pari.tools.output_reader import ReadToolOutputTool
from pari.tools.search import FindFilesTool, GrepTool


class ToolArgumentError(ValueError):
    """Arguments do not match the tool's parameter schema."""


class ToolRegistry:
    """Registry maintaining active agent tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a new tool instance."""
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> Tool | None:
        """Look up tool by name."""
        return self._tools.get(name)

    def get_schemas(self) -> list[dict[str, Any]]:
        """Return list of JSON schemas for all registered tools."""
        return [tool.definition.to_schema() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch tool execution by name with given arguments."""
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        try:
            arguments = coerce_arguments(tool.definition.parameters, arguments)
        except ToolArgumentError as exc:
            return {"error": f"{name}: {exc}"}
        return await tool.execute(**arguments)


def get_default_registry(
    workspace: Path,
    edit_fallback: str = "none",
    sandbox_mode: str | None = None,
) -> ToolRegistry:
    """Instantiate and register the standard PARI tool suite for a given workspace.

    edit_fallback is ``none`` or ``cascade``. Exact replacement stays the default.
    """
    registry = ToolRegistry()
    # One queue so read, write, and edit of the same file share a lock.
    queue = FileMutationQueue(workspace)
    spool_dir = workspace / ".pari" / "tool-outputs"
    for tool in (
        BashTool(
            workspace,
            spooler=ManagedOutputSpooler(spool_dir),
            sandbox_mode=sandbox_mode,
        ),
        ReadFileTool(workspace, queue=queue),
        WriteFileTool(workspace, queue=queue),
        EditFileTool(workspace, queue=queue, edit_fallback=edit_fallback),
        FindFilesTool(workspace),
        GrepTool(workspace),
        ReadToolOutputTool(spool_dir),
    ):
        registry.register(tool)
    return registry


def coerce_arguments(
    schema: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    """Coerce number, integer, and boolean values. Other mismatches are errors."""
    if not isinstance(arguments, dict):
        raise ToolArgumentError("arguments must be an object")
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    required = schema.get("required")
    if not isinstance(required, list):
        required = []
    errors: list[str] = []
    unknown = sorted(set(arguments) - set(properties))
    if unknown:
        names = ", ".join(unknown)
        errors.append(f"unknown arguments: {names}")
    coerced: dict[str, Any] = {}
    for name, spec in properties.items():
        if name not in arguments or arguments[name] is None:
            if name in required:
                errors.append(f"{name} is required")
            continue
        kind = spec.get("type") if isinstance(spec, dict) else None
        try:
            coerced[name] = _coerce(kind, arguments[name], name)
        except ToolArgumentError as exc:
            errors.append(str(exc))
    if errors:
        raise ToolArgumentError("; ".join(errors))
    return coerced


def _coerce(kind: object, value: Any, name: str) -> Any:
    if kind == "number":
        return _number(value, name)
    if kind == "integer":
        return _integer(value, name)
    if kind == "boolean":
        return _boolean(value, name)
    if kind == "string":
        if isinstance(value, str):
            return value
        raise ToolArgumentError(f"{name} must be a string, got {value!r}")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ToolArgumentError(f"{name} must be a number, got {value!r}")
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            raise ToolArgumentError(f"{name} must be a number, got {value!r}") from None
    return float(value)


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ToolArgumentError(f"{name} must be an integer, got {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            number = None
        if number is not None and number.is_integer():
            return int(number)
    raise ToolArgumentError(f"{name} must be an integer, got {value!r}")


def _boolean(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise ToolArgumentError(f"{name} must be a boolean, got {value!r}")
