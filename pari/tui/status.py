"""PARI Layer 9: Real-time Cost Meter & Status Tracker.

Architectural Purpose:
    Displays transparent, continuous token consumption and estimated USD cost
    directly in the terminal status bar so developers never suffer billing surprises.
"""

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cached_tokens


class CostMeter:
    """Calculates and tracks real-time USD cost based on model pricing tiers."""

    # Pricing per million tokens: (input_per_m, output_per_m, cache_read_per_m)
    PRICING_TIERS: ClassVar[dict[str, tuple[float, float, float]]] = {
        "claude-3-7-sonnet": (3.00, 15.00, 0.30),
        "claude-3-5-sonnet": (3.00, 15.00, 0.30),
        "gpt-4o": (2.50, 10.00, 1.25),
        "pari-core": (3.00, 15.00, 0.30),
    }

    def __init__(self, model_family: str = "pari-core"):
        self.model_family = model_family.lower()
        self.usage = TokenUsage()

    def add_usage(self, in_tokens: int, out_tokens: int, cached: int = 0) -> None:
        """Record token consumption."""
        self.usage.input_tokens += max(0, in_tokens)
        self.usage.output_tokens += max(0, out_tokens)
        self.usage.cached_tokens += max(0, cached)

    def calculate_cost_usd(self) -> float:
        """Compute estimated USD cost."""
        default = self.PRICING_TIERS["pari-core"]
        rates = self.PRICING_TIERS.get(self.model_family, default)
        in_cost = (self.usage.input_tokens / 1_000_000.0) * rates[0]
        out_cost = (self.usage.output_tokens / 1_000_000.0) * rates[1]
        cache_cost = (self.usage.cached_tokens / 1_000_000.0) * rates[2]
        return in_cost + out_cost + cache_cost

    def format_status(self) -> str:
        """Format token and cost string for status bar."""
        total = self.usage.total_tokens
        cost = self.calculate_cost_usd()

        if total >= 1_000_000:
            token_str = f"{total / 1_000_000:.1f}M tokens"
        elif total >= 1_000:
            token_str = f"{total / 1_000:.1f}k tokens"
        else:
            token_str = f"{total} tokens"

        return f"{token_str} · ${cost:.3f}"
