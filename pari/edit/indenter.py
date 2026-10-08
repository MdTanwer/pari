"""PARI Layer 5: Relative Indentation Normalizer.

Architectural Purpose:
    LLMs frequently emit replacement blocks whose leading indentation is offset by
    2 or 4 spaces relative to the target site.
    The RelativeIndenter calculates the delta between the indentation of the first line
    of the search block and the replacement block, normalizing subsequent lines.
"""


def align_replacement(window: str, search: str, replace: str) -> str:
    """Re-indent a replacement onto the file lines it matched.

    Same-length blocks keep any extra indent the replacement added on top of
    the search block. Other shapes only shift the base indent.
    """
    window_lines = window.splitlines()
    search_lines = search.splitlines()
    replace_lines = replace.splitlines()
    if len(window_lines) != len(replace_lines) or len(search_lines) != len(
        replace_lines
    ):
        return normalize_relative_indentation(window, replace)
    aligned = [
        _apply_delta(current, old, new)
        for current, old, new in zip(
            window_lines, search_lines, replace_lines, strict=True
        )
    ]
    text = "\n".join(aligned)
    if replace.endswith("\n"):
        text += "\n"
    return text


def normalize_relative_indentation(search_block: str, replace_block: str) -> str:
    """Shift the replacement so its base indent matches the search block."""
    target = _base_indent(search_block)
    source = _base_indent(replace_block)
    if target == source:
        return replace_block
    shifted: list[str] = []
    for line in replace_block.splitlines():
        if line.strip() and (source == "" or line.startswith(source)):
            shifted.append(target + line[len(source) :])
        else:
            shifted.append(line)
    text = "\n".join(shifted)
    if replace_block.endswith("\n"):
        text += "\n"
    return text


def _apply_delta(file_line: str, search_line: str, replace_line: str) -> str:
    if not replace_line.strip():
        return replace_line
    file_indent = _leading(file_line) if file_line.strip() else ""
    search_indent = _leading(search_line) if search_line.strip() else ""
    replace_indent = _leading(replace_line)
    if search_indent and replace_indent.startswith(search_indent):
        extra = replace_indent[len(search_indent) :]
    else:
        extra = ""
    return file_indent + extra + replace_line.lstrip(" \t")


def _leading(line: str) -> str:
    stripped = line.lstrip(" \t")
    return line[: len(line) - len(stripped)]


def _base_indent(block: str) -> str:
    for line in block.splitlines():
        if line.strip():
            stripped = line.lstrip(" \t")
            return line[: len(line) - len(stripped)]
    return ""
