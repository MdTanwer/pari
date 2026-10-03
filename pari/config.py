"""PARI Global Configuration and Runtime Settings.

Encapsulates global agent options, model parameters, timeouts, and sandbox preferences.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PariConfig:
    workspace: Path
    model: str = "claude-3-7-sonnet"
    sandbox_mode: Optional[str] = None
    max_turns: int = 25
    auto_approve: bool = False
    debug: bool = False

    @classmethod
    def from_env(cls, workspace: Optional[Path] = None) -> "PariConfig":
        """Load configuration options from environment variables and CLI defaults."""
        raise NotImplementedError
