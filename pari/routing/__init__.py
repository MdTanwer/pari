"""PARI Layer 8: Dual-Model Routing Engine.

Architectural Purpose:
    Harvested from Aider's architect_coder.py and closes Antigravity F1 (planning token burn).
    Reduces per-turn output costs by ~85%:
    - Architect Model (Claude 3.7 Sonnet / o3-mini): Ingests context and emits a dense,
      high-signal 300-token plan.
    - Editor Model (Claude 3.5 Haiku / DeepSeek V3): Ingests the plan and emits mechanical diffs.

Subsystems:
    - router: Orchestrates the Architect-to-Editor pipeline
    - classifier: Identifies simple/localized edits to bypass Architect overhead
    - anti_verbosity: Enforces strict 4,096-token ceiling on reasoning to arrest planning loops
"""

from pari.routing.router import DualModelRouter
from pari.routing.classifier import TaskClassifier, TaskComplexity
from pari.routing.anti_verbosity import enforce_planning_ceiling

__all__ = [
    "DualModelRouter",
    "TaskClassifier",
    "TaskComplexity",
    "enforce_planning_ceiling",
]
