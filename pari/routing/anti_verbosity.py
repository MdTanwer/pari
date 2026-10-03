"""PARI Layer 8: Anti-Verbosity Guard.

Architectural Purpose:
    Closes Google Antigravity F1 (200k-400k token burn on meta-planning).
    Places a strict hard token ceiling (default 4,096 tokens) on the Architect model.
    If the Architect fails to conclude its plan within 4k tokens, the output is cut
    and dispatched immediately to the Editor model with instructions to execute
    the partial plan, arresting recursive planning loops.
"""

def enforce_planning_ceiling(plan_text: str, max_tokens: int = 4096) -> str:
    """Enforce token ceiling on architect reasoning output."""
    max_chars = max_tokens * 4
    if len(plan_text) <= max_chars:
        return plan_text

    cutoff = plan_text[:max_chars]
    return (
        f"{cutoff}\n\n"
        "[PARI ANTI-VERBOSITY GUARD: Plan cut off at 4,096 tokens to prevent infinite planning loops. "
        "Proceed immediately to execute the above architectural steps.]"
    )
