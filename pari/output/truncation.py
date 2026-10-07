"""PARI Layer 7: Head/Tail Truncation with Context Preservation.

Architectural Purpose:
    When output exceeds the context budget:
    1. Keeps the first N lines (command launch, build headers).
    2. Keeps the last M lines (stack traces, exit assertions, summary errors).
    3. Injects a clear omission notice linking to the disk sidecar containing full raw
    output.
"""


def extract_head_tail(
    text: str,
    head_lines: int = 50,
    tail_lines: int = 100,
    sidecar_path: str = "",
) -> tuple[str, bool]:
    """Truncate text by extracting head and tail sections if line count is high."""
    raise NotImplementedError
