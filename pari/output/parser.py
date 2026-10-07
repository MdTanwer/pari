"""PARI Layer 7: Structured Test Output Parser.

Architectural Purpose:
    Extracts high-signal test failure summaries from raw test output (pytest, jest,
    cargo),
    allowing the model to immediately grasp failing assertions without digesting
    100s of lines of framework internals.
"""


def parse_test_failures(raw_output: str) -> list[str]:
    """Parse failure lines from test runner output."""
    raise NotImplementedError
