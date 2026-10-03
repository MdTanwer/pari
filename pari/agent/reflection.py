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
from typing import Optional


@dataclass
class ReflectionAttempt:
    error_type: str
    error_message: str
    attempt_count: int


class ReflectionManager:
    """Guards reflection retries to prevent unbounded token expenditure."""

    def __init__(self, max_reflections: int = 3):
        self.max_reflections = max_reflections

    def should_retry(self, operation_id: str) -> bool:
        """Check if reflection attempts remain under ceiling."""
        raise NotImplementedError

    def record_failure(self, operation_id: str, error_type: str, message: str) -> str:
        """Format error feedback prompt for next turn."""
        raise NotImplementedError

    def reset(self, operation_id: Optional[str] = None):
        """Clear failure counts."""
        raise NotImplementedError
