"""PARI Layer 9: Real-time Cost Meter & Status Tracker.

Architectural Purpose:
    Displays transparent, continuous token consumption and estimated USD cost
    directly in the terminal status bar so developers never suffer billing surprises.
"""

from dataclasses import dataclass


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0


class CostMeter:
    """Calculates and tracks real-time USD cost based on model pricing tiers."""

    def __init__(self, model_family: str = "claude-3-7-sonnet"):
        self.model_family = model_family

    def add_usage(self, in_tokens: int, out_tokens: int, cached: int = 0):
        """Record token consumption."""
        raise NotImplementedError

    def calculate_cost_usd(self) -> float:
        """Compute estimated USD cost."""
        raise NotImplementedError

    def format_status(self) -> str:
        """Format token and cost string for status bar."""
        raise NotImplementedError
