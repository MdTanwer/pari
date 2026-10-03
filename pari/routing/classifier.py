"""PARI Layer 8: Task Classifier.

Architectural Purpose:
    Evaluates incoming user prompts and active file scope.
    If the task is simple (single file typo, localized test fix, doc update),
    bypasses the Architect model entirely, saving both latency and token cost.
"""

from enum import Enum
import re
from typing import List


class TaskComplexity(str, Enum):
    SIMPLE_EDIT = "simple_edit"      # Bypass architect -> route directly to editor
    ARCHITECTURAL = "architectural"  # Dual-model: Architect plan -> Editor diff


class TaskClassifier:
    """Classifies task complexity to select optimal routing pipeline."""

    @staticmethod
    def classify(prompt: str, active_files: List[str]) -> TaskComplexity:
        lower = prompt.lower()

        # If user explicitly asks for architectural design or refactoring across many files
        if any(w in lower for w in ["refactor", "redesign", "architect", "migrate", "system"]):
            return TaskComplexity.ARCHITECTURAL

        if len(active_files) > 2:
            return TaskComplexity.ARCHITECTURAL

        # Simple localized edit indicators
        if any(w in lower for w in ["typo", "fix line", "rename", "add comment", "format"]):
            return TaskComplexity.SIMPLE_EDIT

        return TaskComplexity.ARCHITECTURAL
