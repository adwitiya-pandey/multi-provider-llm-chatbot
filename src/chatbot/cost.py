"""Token accounting and financial cost tracking per turn and session (SPEC 8, S7)."""

from typing import Any

from chatbot.models import UsageStats

# Pricing per 1,000,000 tokens (USD): (input_rate, output_rate)
# Notional rates for testing and tracking; verified against official pricing on 2026-10-27
DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "gemini-3.8-flash": (
        0.15,
        0.60,
    ),  # Notional, verified on 2026-10-27 from https://ai.google.dev/pricing
    "gemini-3.5-flash-lite": (
        0.075,
        0.30,
    ),  # Notional, verified on 2026-10-27 from https://ai.google.dev/pricing
    "gemini-2.5-flash": (0.15, 0.60),  # Legacy alias
    "gemini-2.5-flash-lite": (0.075, 0.30),  # Legacy alias
    "claude-3-5-haiku-latest": (
        0.80,
        4.00,
    ),  # Verified on 2026-10-27 from https://www.anthropic.com/pricing
    "gpt-4o-mini": (0.15, 0.60),  # Verified on 2026-10-27 from https://openai.com/api/pricing/
    "scripted-demo": (0.15, 0.60),  # Notional (offline demo provider)
}


class BudgetExceededError(Exception):
    """Raised when the session budget ceiling is exceeded."""


class CostTracker:
    """Tracks token consumption and USD costs per turn and cumulatively."""

    def __init__(
        self,
        session_budget_usd: float = 0.50,
        price_table: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        if session_budget_usd <= 0.0:
            raise ValueError("session_budget_usd must be greater than zero")

        self.session_budget_usd = session_budget_usd
        self.price_table = dict(price_table or DEFAULT_PRICING)

        # Cumulative counters
        self.total_turns: int = 0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.cost_by_provider: dict[str, float] = {}

    @property
    def total_tokens(self) -> int:
        """Returns the sum of all input and output tokens consumed."""
        return self.total_input_tokens + self.total_output_tokens

    def check_budget(self) -> None:
        """Raises BudgetExceededError if the cumulative spend has reached or exceeded budget."""
        if self.total_cost_usd >= self.session_budget_usd:
            raise BudgetExceededError(
                f"Session budget of ${self.session_budget_usd:.4f} exceeded "
                f"(current spend: ${self.total_cost_usd:.4f})"
            )

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculates USD cost for given token counts and model pricing."""
        in_rate, out_rate = self.price_table.get(model, (0.15, 0.60))
        cost = (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000.0
        return round(cost, 6)

    def record_turn(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> UsageStats:
        """Records usage and cost for a single turn, updating cumulative totals."""
        turn_cost = self.calculate_cost(model, input_tokens, output_tokens)
        turn_total = input_tokens + output_tokens

        self.total_turns += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd = round(self.total_cost_usd + turn_cost, 6)
        self.cost_by_provider[provider] = round(
            self.cost_by_provider.get(provider, 0.0) + turn_cost, 6
        )

        return UsageStats(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=turn_total,
            cost_usd=turn_cost,
        )

    def get_summary(self) -> dict[str, Any]:
        """Returns session telemetry summary."""
        return {
            "total_turns": self.total_turns,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "budget_usd": self.session_budget_usd,
            "cost_by_provider": dict(self.cost_by_provider),
        }

    def reset(self) -> None:
        """Resets all cumulative counters to zero."""
        self.total_turns = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.cost_by_provider.clear()
