"""PARI Layer 10: Evaluation & Observability Harness.

Architectural Purpose:
    Closes the universal problem of "vibe coding" (subjective prompt tweaking without objective regression tests).
    Provides a deterministic local micro-eval suite ($3-$5 per run) and structured observability.

Subsystems:
    - runner: Micro-eval benchmark runner executing deterministic test cases
    - judge: Cross-model verification judge (Graptile principle: never evaluate with same model family)
    - metrics: Quantitative benchmarks (pass rates, token costs, turn counts)
    - logging: Structured JSON logging (structlog format) for full execution telemetry
"""

from pari.eval.runner import MicroEvalRunner, TestCase, EvalReport
from pari.eval.judge import CrossModelJudge
from pari.eval.metrics import calculate_eval_metrics
from pari.eval.logging import StructuredLogger

__all__ = [
    "MicroEvalRunner",
    "TestCase",
    "EvalReport",
    "CrossModelJudge",
    "calculate_eval_metrics",
    "StructuredLogger",
]
