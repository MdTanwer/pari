"""PARI Layer 7: Managed Output Disk Spooler.

Architectural Purpose:
    Closes Codex F4 (RSS bloat on large outputs) & OpenCode 50KB output cap.
    Streams subprocess output into a temporary disk sidecar file.
    If output exceeds max_bytes (default 50KB) or max_lines (default 2,000 lines),
    it generates a sanitized head/tail summary for prompt injection while preserving
    the full output on disk for on-demand inspection via /spool command.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SpoolResult:
    context_text: str
    sidecar_path: Path
    total_bytes: int
    total_lines: int
    was_truncated: bool


class ManagedOutputSpooler:
    """Spools process output to disk sidecars and extracts safe context summaries."""

    def __init__(self, spool_dir: Optional[Path] = None, max_bytes: int = 50 * 1024):
        self.max_bytes = max_bytes

    def spool(self, raw_output: str, command_tag: str = "cmd") -> SpoolResult:
        """Spool output to disk sidecar and return truncated context text if large."""
        raise NotImplementedError
