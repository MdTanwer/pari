"""PARI Layer 10: Structured Observability Logging.

Emits structured JSON events for monitoring, analysis, and debugging.
Logs events such as tool_call, edit_applied, sandbox_exec, turn_complete.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional


class StructuredLogger:
    """Emits newline-delimited JSON logs to stdout or a designated log file."""

    def __init__(self, log_file: Optional[Path] = None):
        self.log_file = log_file
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event_name: str, **kwargs: Any):
        record: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_name,
            **kwargs,
        }
        line = json.dumps(record)
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        else:
            print(f"[OBSERVABILITY] {line}")
