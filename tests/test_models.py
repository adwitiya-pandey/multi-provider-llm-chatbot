"""Unit tests for Pydantic data models (SPEC 3, S6)."""

import pytest
from pydantic import ValidationError

from chatbot.models import (
    ChatMessage,
    ProviderAttempt,
    StructuredReply,
    TurnResult,
    UsageStats,
    UserTurnInput,
)


def test_user_turn_input_valid_and_strip() -> None:
    inp = UserTurnInput(text="   What is Apache Iceberg?   ")
    assert inp.text == "What is Apache Iceberg?"
    assert inp.domain_focus == "General AI & Data Engineering"


def test_user_turn_input_bounds_and_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        UserTurnInput(text="")

    with pytest.raises(ValidationError):
        UserTurnInput(text="x" * 4001)

    with pytest.raises(ValidationError):
        UserTurnInput(text="hello", extra_field="forbidden")  # type: ignore[call-arg]


def test_chat_message_valid_and_regex() -> None:
    msg = ChatMessage(role="user", content="Hello", turn_id="TURN-0001")
    assert msg.role == "user"
    assert msg.turn_id == "TURN-0001"

    with pytest.raises(ValidationError):
        ChatMessage(role="user", content="Hello", turn_id="INVALID-ID")

    with pytest.raises(ValidationError):
        ChatMessage(role="system", content="Hello", turn_id="TURN-0001")  # type: ignore[arg-type]


def test_structured_reply_valid() -> None:
    reply = StructuredReply(
        answer="Apache Iceberg is an open table format.",
        category="technical",
        key_points=["ACID transactions", "Hidden partitioning"],
        follow_up_questions=["Would you like an example with Spark?"],
        confidence=0.95,
    )
    assert reply.category == "technical"
    assert len(reply.key_points) == 2
    assert reply.confidence == 0.95


def test_structured_reply_validation_errors() -> None:
    # Invalid category
    with pytest.raises(ValidationError):
        StructuredReply(
            answer="Test",
            category="unknown",  # type: ignore[arg-type]
            key_points=["Point 1"],
            follow_up_questions=["Question 1?"],
            confidence=0.5,
        )

    # Empty key points list
    with pytest.raises(ValidationError):
        StructuredReply(
            answer="Test",
            category="general",
            key_points=[],
            follow_up_questions=["Question 1?"],
            confidence=0.5,
        )

    # Confidence out of bounds
    with pytest.raises(ValidationError):
        StructuredReply(
            answer="Test",
            category="general",
            key_points=["Point 1"],
            follow_up_questions=["Question 1?"],
            confidence=1.5,
        )

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        StructuredReply(
            answer="Test",
            category="general",
            key_points=["Point 1"],
            follow_up_questions=["Question 1?"],
            confidence=0.8,
            unexpected_field="disallowed",  # type: ignore[call-arg]
        )


def test_usage_stats_and_turn_result() -> None:
    usage = UsageStats(input_tokens=100, output_tokens=50, total_tokens=150, cost_usd=0.00012)
    assert usage.total_tokens == 150

    attempt = ProviderAttempt(
        provider="scripted",
        model="scripted-demo",
        attempt_number=1,
        success=True,
        error_code=None,
        latency_ms=12.5,
    )

    reply = StructuredReply(
        answer="Sample answer",
        category="general",
        key_points=["Key point"],
        follow_up_questions=["Follow-up?"],
        confidence=1.0,
    )

    result = TurnResult(
        turn_id="TURN-0001",
        reply=reply,
        provider_used="scripted",
        model_used="scripted-demo",
        retries_used=0,
        fallback_used=False,
        repair_used=False,
        injection_flagged=False,
        usage=usage,
        attempts=[attempt],
    )
    assert result.turn_id == "TURN-0001"
    assert not result.fallback_used
