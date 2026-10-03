"""PARI Layer 3: Repo Map Generator & Token Packer.

Architectural Purpose:
    Packs codebase structural symbols into a strict token budget (default 2,048 tokens)
    using binary-search selection based on PPR rankings.
"""

from pathlib import Path
from typing import List, Optional


class RepoMapGenerator:
    """Generates condensed repository map from parsed source symbols."""

    def __init__(self, workspace: Path, max_tokens: int = 2048):
        self.workspace = workspace.resolve()
        self.max_tokens = max_tokens

    def generate(self, focus_files: Optional[List[str]] = None) -> str:
        """Scan workspace, extract symbols, and format condensed outline."""
        raise NotImplementedError
