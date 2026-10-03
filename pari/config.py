"""PARI Global Configuration and Runtime Settings.

Encapsulates global agent options, model parameters, timeouts, and sandbox preferences.
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional


@dataclass
class PariConfig:
    workspace: Path = field(default_factory=Path.cwd)
    model: str = "claude-3-7-sonnet-20250219"
    editor_model: str = "claude-3-5-haiku-20241022"
    sandbox_mode: Optional[str] = None  # "bwrap", "seatbelt", "e2b", "process"
    max_turns: int = 25
    auto_approve: bool = False
    debug: bool = False

    @classmethod
    def from_env(cls, workspace: Optional[Path] = None) -> "PariConfig":
        return cls(
            workspace=(workspace or Path.cwd()).resolve(),
            model=os.environ.get("PARI_MODEL", "claude-3-7-sonnet-20250219"),
            editor_model=os.environ.get("PARI_EDITOR_MODEL", "claude-3-5-haiku-20241022"),
            sandbox_mode=os.environ.get("PARI_SANDBOX_MODE"),
            max_turns=int(os.environ.get("PARI_MAX_TURNS", "25")),
            debug=os.environ.get("PARI_DEBUG", "").lower() in ("1", "true"),
        )
