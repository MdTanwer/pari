"""PARI Layer 4: Reflection & Error Injection Manager.

Architectural Purpose:
    Closes Aider F5 (Reflection loop token burn: $0.50-$2.00 per stubborn diff).
    When a tool call or edit fails:
    1. Formats the error into a high-signal structured diagnostic.
    2. Limits reflection attempts to max_reflections (default: 3).
    3. If 3 attempts fail, halts execution and prompts the user for intervention,
       preventing infinite token-burning retry loops.
"""

from dataclasses import dataclass


@dataclass
class ReflectionAttempt:
    error_type: str
    error_message: str
    attempt_count: int


class ReflectionManager:
    """Guards reflection retries to prevent unbounded token expenditure."""

    def __init__(self, max_reflections: int = 3):
        self.max_reflections = max_reflections
        self._counts: dict[str, int] = {}

    def should_retry(self, operation_id: str) -> bool:
        """True while this operation still has attempts left.

        The count goes up in record_failure. After max_reflections failures
        the loop must stop and ask the user instead of calling the model again.
        """
        return self._counts.get(operation_id, 0) < self.max_reflections

    def record_failure(self, operation_id: str, error_type: str, message: str) -> str:
        """Count the failure and return the prompt block for the next turn."""
        count = self._counts.get(operation_id, 0) + 1
        self._counts[operation_id] = count
        attempt = ReflectionAttempt(error_type, message, count)
        if count >= self.max_reflections:
            ending = " Reflection limit reached. Stop and ask the user."
        else:
            ending = " Retry with a smaller, targeted change."
        return (
            f"[{attempt.error_type}] attempt {attempt.attempt_count}"
            f"/{self.max_reflections}: {attempt.error_message}.{ending}"
        )

    def reset(self, operation_id: str | None = None) -> None:
        """Clear failure counts for one operation, or for every operation."""
        if operation_id is None:
            self._counts.clear()
            return
        self._counts.pop(operation_id, None)


def format_lint_error(
    path: str,
    line_number: int,
    enclosing: str,
    window: str,
) -> str:
    """Build the short lint block the loop injects after a failed edit.

    The window should already be the few lines around the error. This function
    does not read the file, so it cannot pull a whole compiler log back in.
    """
    return (
        f"[LINT ERROR] In {path}:{line_number}:\n"
        f"Enclosing function: {enclosing}\n"
        f"{window}\n"
        "Fix the specific error above using a targeted search/replace edit."
    )
