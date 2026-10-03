"""PARI Layer 5: Relative Indentation Normalizer.

Architectural Purpose:
    LLMs frequently emit replacement blocks whose leading indentation is offset by
    2 or 4 spaces relative to the target site.
    The RelativeIndenter calculates the delta between the indentation of the first line
    of the search block and the replacement block, normalizing subsequent lines.
"""

def normalize_relative_indentation(search_block: str, replace_block: str) -> str:
    """Normalize indentation of replacement block to match search block site."""
    raise NotImplementedError
