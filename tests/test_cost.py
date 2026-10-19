"""Unit tests for token accounting and cost tracking (SPEC 8, S7)."""

import pytest

from chatbot.cost import BudgetExceededError, CostTracker


def test_per_model_pricing_math() -> None:
    tracker = CostTracker(session_budget_usd=10.0)

    # 1M input ($0.15) + 1M output ($0.60) for gemini-2.5-flash = $0.75
    cost_flash = tracker.calculate_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
    assert pytest.approx(cost_flash, rel=1e-4) == 0.75

    # 1M input ($0.80) + 1M output ($4.00) for claude-3-5-haiku-latest = $4.80
    cost_haiku = tracker.calculate_cost("claude-3-5-haiku-latest", 1_000_000, 1_000_000)
    assert pytest.approx(cost_haiku, rel=1e-4) == 4.80


def test_record_turn_and_cumulative_totals() -> None:
    tracker = CostTracker(session_budget_usd=1.0)

    stats1 = tracker.record_turn(
        provider="gemini",
        model="gemini-2.5-flash",
        input_tokens=1000,
        output_tokens=500,
    )
    assert stats1.input_tokens == 1000
    assert stats1.output_tokens == 500
    assert stats1.total_tokens == 1500
    assert stats1.cost_usd > 0.0

    stats2 = tracker.record_turn(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=2000,
        output_tokens=1000,
    )
    assert stats2.total_tokens == 3000

    summary = tracker.get_summary()
    assert summary["total_turns"] == 2
    assert summary["total_input_tokens"] == 3000
    assert summary["total_output_tokens"] == 1500
    assert summary["total_tokens"] == 4500
    assert "gemini" in summary["cost_by_provider"]
    assert "openai" in summary["cost_by_provider"]


def test_budget_ceiling_raises_error() -> None:
    # Set ceiling to $0.05
    tracker = CostTracker(session_budget_usd=0.05)
    tracker.check_budget()  # Should not raise initially

    # Record turn that pushes cost to $0.06
    tracker.record_turn(
        provider="anthropic",
        model="claude-3-5-haiku-latest",
        input_tokens=50_000,
        output_tokens=10_000,
    )
    assert tracker.total_cost_usd >= 0.05

    with pytest.raises(BudgetExceededError, match="Session budget of \\$0.0500 exceeded"):
        tracker.check_budget()


def test_reset_cost_tracker() -> None:
    tracker = CostTracker(session_budget_usd=0.50)
    tracker.record_turn("scripted", "scripted-demo", 100, 50)
    assert tracker.total_turns == 1

    tracker.reset()
    assert tracker.total_turns == 0
    assert tracker.total_cost_usd == 0.0
    assert tracker.total_tokens == 0
    assert len(tracker.cost_by_provider) == 0


def test_invalid_budget() -> None:
    with pytest.raises(ValueError, match="session_budget_usd"):
        CostTracker(session_budget_usd=0.0)
