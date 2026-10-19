"""Unit tests for sliding-window conversation memory (SPEC 7)."""

import pytest

from chatbot.memory import ConversationMemory, estimate_tokens
from chatbot.models import StructuredReply, UserTurnInput


def _create_sample_reply(answer: str = "Test answer") -> StructuredReply:
    return StructuredReply(
        answer=answer,
        category="general",
        key_points=["Point A", "Point B"],
        follow_up_questions=["Question 1?"],
        confidence=0.9,
    )


def test_estimate_tokens() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("hello world") == 2
    assert estimate_tokens("a" * 100) == 25


def test_turn_count_limit_eviction() -> None:
    mem = ConversationMemory(max_turns=3, max_estimated_tokens=10000)

    for i in range(1, 6):
        inp = UserTurnInput(text=f"Question {i}")
        rep = _create_sample_reply(f"Answer {i}")
        mem.add_turn(inp, rep, turn_id=f"TURN-{i:04d}")

    assert mem.turn_count == 3
    stored_ids = [turn.turn_id for turn in mem.turns]
    assert stored_ids == ["TURN-0003", "TURN-0004", "TURN-0005"]


def test_token_budget_eviction() -> None:
    # Set a small token budget so adding turns causes token-based eviction
    mem = ConversationMemory(max_turns=10, max_estimated_tokens=100)

    # Each turn here will have ~50+ estimated tokens
    inp1 = UserTurnInput(text="Short query 1")
    rep1 = _create_sample_reply("x" * 160)
    mem.add_turn(inp1, rep1, turn_id="TURN-0001")

    inp2 = UserTurnInput(text="Short query 2")
    rep2 = _create_sample_reply("y" * 160)
    mem.add_turn(inp2, rep2, turn_id="TURN-0002")

    inp3 = UserTurnInput(text="Short query 3")
    rep3 = _create_sample_reply("z" * 160)
    mem.add_turn(inp3, rep3, turn_id="TURN-0003")

    assert mem.estimated_tokens <= 100
    assert mem.turn_count < 3


def test_to_provider_messages() -> None:
    mem = ConversationMemory(max_turns=5, max_estimated_tokens=5000)
    inp = UserTurnInput(text="What is streaming?")
    rep = _create_sample_reply("Streaming transmits data incrementally.")
    mem.add_turn(inp, rep, turn_id="TURN-0001")

    messages = mem.to_provider_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is streaming?"
    assert messages[1]["role"] == "assistant"
    assert "Streaming transmits data incrementally." in messages[1]["content"]


def test_clear_memory() -> None:
    mem = ConversationMemory(max_turns=5, max_estimated_tokens=5000)
    mem.add_turn(UserTurnInput(text="Q1"), _create_sample_reply("A1"))
    assert mem.turn_count == 1
    mem.clear()
    assert mem.turn_count == 0
    assert mem.estimated_tokens == 0


def test_invalid_init_parameters() -> None:
    with pytest.raises(ValueError, match="max_turns"):
        ConversationMemory(max_turns=0)

    with pytest.raises(ValueError, match="max_estimated_tokens"):
        ConversationMemory(max_turns=5, max_estimated_tokens=50)
