"""PARI Layer 7: Managed Output Disk Spooler.

Architectural Purpose:
    Closes Codex F4 (RSS bloat on large outputs) & OpenCode 50KB output cap.
    Streams subprocess output into a temporary disk sidecar file.
    If output exceeds max_bytes (default 50KB) or max_lines (default 2,000 lines),
    it generates a sanitized head/tail summary for prompt injection while preserving
    the full output on disk for on-demand inspection via /spool command.
"""

import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from pari.output.truncation import extract_head_tail


@dataclass
class SpoolResult:
    context_text: str
    sidecar_path: Path
    total_bytes: int
    total_lines: int
    was_truncated: bool


_DEFAULT_MAX_LINES = 2000
_SIDECAR_TTL_SECONDS = 7 * 24 * 60 * 60


class ManagedOutputSpooler:
    """Spools process output to disk sidecars and extracts safe context summaries."""

    def __init__(
        self,
        spool_dir: Path | None = None,
        max_bytes: int = 50 * 1024,
        max_lines: int = _DEFAULT_MAX_LINES,
    ):
        self.spool_dir = spool_dir
        self.max_bytes = max_bytes
        self.max_lines = max_lines

    def spool(self, raw_output: str, command_tag: str = "cmd") -> SpoolResult:
        """Write the full log, then return a bounded view for the prompt.

        The sidecar is written before the size check so a later crash still
        leaves the complete output on disk.
        """
        if self.spool_dir is None:
            raise ValueError("spool_dir is required")
        self.spool_dir.mkdir(parents=True, exist_ok=True)
        safe_tag = "".join(ch for ch in command_tag if ch.isalnum()) or "cmd"
        sidecar = self.spool_dir / f"{safe_tag}-{uuid.uuid4().hex}.txt"
        sidecar.write_text(raw_output, encoding="utf-8")
        total_bytes = len(raw_output.encode("utf-8"))
        total_lines = len(raw_output.splitlines())
        over_budget = total_bytes > self.max_bytes or total_lines > self.max_lines
        if not over_budget:
            return SpoolResult(
                context_text=raw_output,
                sidecar_path=sidecar,
                total_bytes=total_bytes,
                total_lines=total_lines,
                was_truncated=False,
            )
        context_text, _truncated = extract_head_tail(
            raw_output,
            head_lines=20,
            tail_lines=20,
            sidecar_path=str(sidecar),
        )
        return SpoolResult(
            context_text=context_text,
            sidecar_path=sidecar,
            total_bytes=total_bytes,
            total_lines=total_lines,
            was_truncated=True,
        )

    def purge_expired(self, now: float | None = None) -> int:
        """Delete sidecars older than seven days. Returns how many were removed."""
        if self.spool_dir is None or not self.spool_dir.is_dir():
            return 0
        current = time.time() if now is None else now
        removed = 0
        for path in self.spool_dir.glob("*.txt"):
            age = current - path.stat().st_mtime
            if age <= _SIDECAR_TTL_SECONDS:
                continue
            path.unlink()
            removed += 1
        return removed
