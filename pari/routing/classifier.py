"""PARI Layer 8: Task Classifier.

Architectural Purpose:
    Evaluates incoming user prompts and active file scope.
    If the task is simple (single file typo, localized test fix, doc update),
    bypasses the Architect model entirely, saving both latency and token cost.
"""

from enum import StrEnum


class TaskComplexity(StrEnum):
    SIMPLE_EDIT = "simple_edit"  # Bypass architect -> route directly to editor
    ARCHITECTURAL = "architectural"  # Dual-model: Architect plan -> Editor diff


# A prompt that says one of these, or that already touches three files,
# goes to the architect. A one-file typo does not.
_ARCHITECT_WORDS = ("architect", "refactor", "design", "how should")


class TaskClassifier:
    """Classifies task complexity to select optimal routing pipeline."""

    @staticmethod
    def classify(prompt: str, active_files: list[str]) -> TaskComplexity:
        """Three or more files, or a design word, selects the architect."""
        if len(active_files) >= 3:
            return TaskComplexity.ARCHITECTURAL
        text = prompt.lower()
        if any(word in text for word in _ARCHITECT_WORDS):
            return TaskComplexity.ARCHITECTURAL
        return TaskComplexity.SIMPLE_EDIT
