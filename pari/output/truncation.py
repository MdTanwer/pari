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
    """Keep the launch header and the trailing traceback.

    The middle is replaced by a notice that contains OMITTED and the sidecar
    path. A caller can search for that word to tell a window from the full log.
    """
    lines = text.splitlines()
    if len(lines) <= head_lines + tail_lines:
        return text, False
    omitted = len(lines) - head_lines - tail_lines
    notice = f"... [OMITTED {omitted} lines. Full log: {sidecar_path}] ..."
    window = lines[:head_lines] + [notice] + lines[-tail_lines:]
    return "\n".join(window), True
