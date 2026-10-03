"""PARI Layer 3: Substring & Globbing Search Engine (v1 Baseline Navigation).

Architectural Purpose:
    Provides fast, deterministic code search without requiring C-extension compilation.
    Enforces ignore boundaries (.git, .venv, node_modules, build artifacts).
"""

from pathlib import Path
from typing import List, Optional
from pari.search import find_files, grep_search, GrepMatch

__all__ = ["find_files", "grep_search", "GrepMatch"]
