"""PARI Layer 7: Head/Tail Truncation with Context Preservation.

Architectural Purpose:
    When output exceeds the context budget:
    1. Keeps the first N lines (command launch, build headers).
    2. Keeps the last M lines (stack traces, exit assertions, summary errors).
    3. Injects a clear omission notice linking to the disk sidecar containing full raw output.
"""

from typing import Tuple


def extract_head_tail(
    text: str,
    head_lines: int = 50,
    tail_lines: int = 100,
    sidecar_path: str = "",
) -> Tuple[str, bool]:
    """Truncate text by extracting head and tail sections if line count is high.
    
    Returns:
        (condensed_text, was_truncated)
    """
    lines = text.splitlines()
    total_lines = len(lines)

    if total_lines <= (head_lines + tail_lines):
        return text, False

    head = lines[:head_lines]
    tail = lines[-tail_lines:]
    omitted = total_lines - (head_lines + tail_lines)

    notice = (
        f"\n... [PARI OUTPUT HYGIENE: OMITTED {omitted} INTERMEDIATE LINES] ...\n"
        f"Full raw output saved to sidecar: {sidecar_path}\n"
    )

    condensed = "\n".join(head) + "\n" + notice + "\n".join(tail)
    return condensed, True
