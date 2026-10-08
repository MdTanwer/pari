"""PARI Tools: paged reads of spooled command output.

The model uses this instead of re-running a command whose log was truncated.
"""

from pathlib import Path

from pari.tools.base import Tool, ToolDefinition


_PAGE_LIMIT = 45_000


class ReadToolOutputTool(Tool):
    """Read a byte window of a sidecar under the spool directory."""

    def __init__(self, spool_dir: Path):
        self.spool_dir = spool_dir

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read_tool_output",
            description="Read a slice of a spooled command log.",
            parameters={
                "type": "object",
                "properties": {
                    "sidecar_path": {
                        "type": "string",
                        "description": "Path returned with a truncated command.",
                    },
                    "offset_bytes": {
                        "type": "integer",
                        "description": "Byte offset to start from.",
                    },
                    "limit_bytes": {
                        "type": "integer",
                        "description": "Maximum bytes to return.",
                    },
                },
                "required": ["sidecar_path"],
            },
        )

    async def execute(
        self,
        sidecar_path: str,
        offset_bytes: int = 0,
        limit_bytes: int = _PAGE_LIMIT,
    ) -> str:
        """Read one page. Paths outside the spool directory are rejected."""
        target = _sidecar_file(self.spool_dir, sidecar_path)
        data = target.read_bytes()
        start = max(offset_bytes, 0)
        page = data[start : start + max(limit_bytes, 0)]
        text = page.decode("utf-8", errors="replace")
        return f"[PAGED OUTPUT: offset={start}, bytes_read={len(page)}]\n{text}"


def _sidecar_file(spool_dir: Path, sidecar_path: str) -> Path:
    """Resolve a sidecar and refuse anything outside the spool directory."""
    root = spool_dir.resolve()
    candidate = Path(sidecar_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError(
            f"Sidecar path escapes the spool directory: {sidecar_path}"
        ) from exc
    if not resolved.is_file():
        raise FileNotFoundError(sidecar_path)
    return resolved
