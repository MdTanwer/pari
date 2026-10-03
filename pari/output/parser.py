"""PARI Layer 7: Structured Test Output Parser.

Architectural Purpose:
    Extracts high-signal test failure summaries from raw test output (pytest, jest, cargo),
    allowing the model to immediately grasp failing assertions without digesting
    100s of lines of framework internals.
"""

import re
from typing import List


def parse_test_failures(raw_output: str) -> List[str]:
    """Parse failure lines from test runner output."""
    failures = []
    lines = raw_output.splitlines()

    # Pytest failure patterns
    in_failures = False
    for line in lines:
        if line.startswith("FAILED ") or line.startswith("FAIL "):
            failures.append(line.strip())
        elif line.startswith("=== FAILURES ==="):
            in_failures = True
        elif in_failures and line.startswith("E   "):
            failures.append(line.strip())

    return failures
