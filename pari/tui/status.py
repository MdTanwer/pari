"""PARI Layer 9: Real-time Cost Meter & Status Tracker.

Architectural Purpose:
    Displays transparent, continuous token consumption and estimated USD cost
    directly in the terminal status bar so developers never suffer billing surprises.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0


class CostMeter:
    """Calculates and tracks real-time USD cost based on model pricing tiers."""

    PRICING = {
        "claude-3-7-sonnet": {"in": 3.00, "out": 15.00, "cache": 0.375},
        "claude-3-5-haiku": {"in": 0.80, "out": 4.00, "cache": 0.08},
        "gpt-4o": {"in": 2.50, "out": 10.00, "cache": 1.25},
        "deepseek-chat": {"in": 0.27, "out": 1.10, "cache": 0.07},
        "local": {"in": 0.0, "out": 0.0, "cache": 0.0},
    }

    def __init__(self, model_family: str = "claude-3-7-sonnet"):
        self.model_family = model_family
        self.usage = TokenUsage()

    def add_usage(self, in_tokens: int, out_tokens: int, cached: int = 0):
        self.usage.input_tokens += in_tokens
        self.usage.output_tokens += out_tokens
        self.usage.cached_tokens += cached

    def calculate_cost_usd(self) -> float:
        rates = self.PRICING.get(self.model_family, self.PRICING["claude-3-7-sonnet"])
        cost = (
            (self.usage.input_tokens / 1_000_000) * rates["in"]
            + (self.usage.output_tokens / 1_000_000) * rates["out"]
            + (self.usage.cached_tokens / 1_000_000) * rates["cache"]
        )
        return cost

    def format_status(self) -> str:
        cost = self.calculate_cost_usd()
        total_tokens = self.usage.input_tokens + self.usage.output_tokens
        return f"[Tokens: {total_tokens:,} | Cost: ${cost:.4f}]"
