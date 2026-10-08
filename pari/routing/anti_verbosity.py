"""PARI Layer 8: Anti-Verbosity Guard.

Architectural Purpose:
    Closes Google Antigravity F1 (200k-400k token burn on meta-planning).
    Places a strict hard token ceiling (default 4,096 tokens) on the Architect model.
    If the Architect fails to conclude its plan within 4k tokens, the output is cut
    and dispatched immediately to the Editor model with instructions to execute
    the partial plan, arresting recursive planning loops.
"""

_CHARS_PER_TOKEN = 4
_NOTICE = "[PARI ANTI-VERBOSITY GUARD: planning cut at the token ceiling]"


def enforce_planning_ceiling(plan_text: str, max_tokens: int = 4096) -> str:
    """Cut a plan that ran past the ceiling. A short plan is returned whole."""
    limit = max(0, max_tokens) * _CHARS_PER_TOKEN
    if len(plan_text) <= limit:
        return plan_text
    return plan_text[:limit].rstrip() + "\n" + _NOTICE
