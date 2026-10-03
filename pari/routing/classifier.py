"""PARI Layer 8: Task Classifier.

Architectural Purpose:
    Evaluates incoming user prompts and active file scope.
    If the task is simple (single file typo, localized test fix, doc update),
    bypasses the Architect model entirely, saving both latency and token cost.
"""

from enum import Enum
from typing import List


class TaskComplexity(str, Enum):
    SIMPLE_EDIT = "simple_edit"      # Bypass architect -> route directly to editor
    ARCHITECTURAL = "architectural"  # Dual-model: Architect plan -> Editor diff


class TaskClassifier:
    """Classifies task complexity to select optimal routing pipeline."""

    @staticmethod
    def classify(prompt: str, active_files: List[str]) -> TaskComplexity:
        """Classify task complexity based on intent keywords and scope."""
        raise NotImplementedError
