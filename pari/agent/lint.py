"""Syntax check for a file the loop just wrote.

The check uses the standard library parser. It returns a short window around
the failing line so the next model turn does not receive a compiler log.
"""

import ast

from pari.agent.reflection import format_lint_error


def lint_python(path: str, source: str) -> str | None:
    """Return a lint block when path is Python and source does not parse."""
    if not path.endswith(".py"):
        return None
    try:
        ast.parse(source)
    except SyntaxError as exc:
        line = exc.lineno or 1
        return format_lint_error(
            path,
            line,
            _enclosing(source, line),
            _window(source, line, exc.msg),
        )
    return None


def _enclosing(source: str, line: int) -> str:
    rows = source.splitlines()
    last = min(line, len(rows)) - 1
    for index in range(last, -1, -1):
        stripped = rows[index].lstrip()
        if stripped.startswith(("def ", "async def ", "class ")):
            return stripped
    return "<module>"


def _window(source: str, line: int, message: str) -> str:
    rows = source.splitlines()
    start = max(line - 5, 1)
    end = min(line + 5, len(rows))
    shown: list[str] = []
    for number in range(start, end + 1):
        text = rows[number - 1] if number <= len(rows) else ""
        if number == line:
            text = f"{text}  # {message}"
        shown.append(f"{number}: {text}")
    return "\n".join(shown)
