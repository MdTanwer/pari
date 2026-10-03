"""Unit tests for Layer 8 Dual-Model Routing & Anti-Verbosity Guard."""

from pari.routing.classifier import TaskClassifier, TaskComplexity
from pari.routing.anti_verbosity import enforce_planning_ceiling


def test_task_classifier():
    c1 = TaskClassifier.classify("Fix typo in README", ["README.md"])
    assert c1 == TaskComplexity.SIMPLE_EDIT

    c2 = TaskClassifier.classify("Redesign system architecture", ["a.py", "b.py", "c.py", "d.py"])
    assert c2 == TaskComplexity.ARCHITECTURAL


def test_anti_verbosity_ceiling():
    small_plan = "Step 1: Edit file\nStep 2: Run tests"
    assert enforce_planning_ceiling(small_plan, max_tokens=100) == small_plan

    large_plan = "plan line\n" * 1000
    capped = enforce_planning_ceiling(large_plan, max_tokens=50)
    assert "[PARI ANTI-VERBOSITY GUARD" in capped
