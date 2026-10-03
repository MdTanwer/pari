"""PARI Layer 7: Managed Output Disk Spooler.

Architectural Purpose:
    Closes Codex F4 (RSS bloat on large outputs) & OpenCode 50KB output cap.
    Streams subprocess output into a temporary disk sidecar file.
    If output exceeds max_bytes (default 50KB) or max_lines (default 2,000 lines),
    it generates a sanitized head/tail summary for prompt injection while preserving
    the full output on disk for on-demand inspection via /spool command.
"""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import time
from typing import Optional
from pari.output.truncation import extract_head_tail


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
        self.spool_dir = spool_dir or (Path.home() / ".cache" / "pari" / "spool")
        self.spool_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes

    def spool(self, raw_output: str, command_tag: str = "cmd") -> SpoolResult:
        encoded = raw_output.encode("utf-8")
        total_bytes = len(encoded)
        total_lines = len(raw_output.splitlines())

        timestamp = int(time.time() * 1000)
        h = hashlib.sha256(encoded[:512]).hexdigest()[:8]
        sidecar_file = self.spool_dir / f"{command_tag}_{timestamp}_{h}.log"
        sidecar_file.write_bytes(encoded)

        if total_bytes <= self.max_bytes and total_lines <= 150:
            return SpoolResult(
                context_text=raw_output,
                sidecar_path=sidecar_file,
                total_bytes=total_bytes,
                total_lines=total_lines,
                was_truncated=False,
            )

        condensed, truncated = extract_head_tail(
            raw_output,
            head_lines=40,
            tail_lines=80,
            sidecar_path=str(sidecar_file),
        )

        return SpoolResult(
            context_text=condensed,
            sidecar_path=sidecar_file,
            total_bytes=total_bytes,
            total_lines=total_lines,
            was_truncated=True,
        )
