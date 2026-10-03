"""PARI Layer 5: Relative Indentation Normalizer.

Architectural Purpose:
    LLMs frequently emit replacement blocks whose leading indentation is offset by
    2 or 4 spaces relative to the target site.
    The RelativeIndenter calculates the delta between the indentation of the first line
    of the search block and the replacement block, normalizing subsequent lines.
"""

def normalize_relative_indentation(search_block: str, replace_block: str) -> str:
    """Normalize indentation of replacement block to match search block site."""
    search_lines = search_block.splitlines()
    replace_lines = replace_block.splitlines()

    if not search_lines or not replace_lines:
        return replace_block

    def get_indent(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    search_indent = get_indent(search_lines[0])
    replace_indent = get_indent(replace_lines[0])
    delta = search_indent - replace_indent

    if delta == 0:
        return replace_block

    adjusted_lines = []
    for line in replace_lines:
        if not line.strip():
            adjusted_lines.append(line)
        elif delta > 0:
            adjusted_lines.append(" " * delta + line)
        else:
            # Drop leading spaces up to abs(delta)
            to_remove = min(abs(delta), get_indent(line))
            adjusted_lines.append(line[to_remove:])

    return "\n".join(adjusted_lines)
