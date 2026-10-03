"""PARI Layer 10: Quantitative Evaluation Metrics.

Computes pass rate, mean cost per resolved task, mean turns, and duration.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class EvalMetrics:
    total_tasks: int
    passed_tasks: int
    pass_rate: float
    total_cost_usd: float
    mean_cost_per_task: float
    mean_turns: float


def calculate_eval_metrics(results: List[dict]) -> EvalMetrics:
    total = len(results)
    if total == 0:
        return EvalMetrics(0, 0, 0.0, 0.0, 0.0, 0.0)

    passed = sum(1 for r in results if r.get("passed", False))
    total_cost = sum(r.get("cost_usd", 0.0) for r in results)
    total_turns = sum(r.get("turns", 0) for r in results)

    return EvalMetrics(
        total_tasks=total,
        passed_tasks=passed,
        pass_rate=(passed / total) * 100.0,
        total_cost_usd=total_cost,
        mean_cost_per_task=total_cost / total,
        mean_turns=total_turns / total,
    )
