"""Unit tests for TokenCounter, TiktokenCounter, HeuristicCounter, and budget pre-checks."""

import logging
from typing import Any

import pytest

from chatbot.chat import ChatOrchestrator
from chatbot.cost import BudgetExceededError, CostTracker
from chatbot.memory import ConversationMemory
from chatbot.models import ProviderName, StructuredReply, UserTurnInput
from chatbot.providers import ProviderResponse
from chatbot.resilience import ResilientRouter
from chatbot.tokens import (
    HeuristicCounter,
    TiktokenCounter,
    get_counter,
)

# Reference sample reply for memory testing
SAMPLE_REPLY = StructuredReply(
    answer="Indexing speeds up queries by maintaining an ordered B-Tree structure.",
    category="technical",
    key_points=["B-Tree index", "O(log N) lookup", "Write overhead"],
    follow_up_questions=["Would you like an example of composite indexes?"],
    confidence=0.95,
)


class MockAuditHandler(logging.Handler):
    """In-memory logging handler capturing structured log events for inspection."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class SpyQueueProvider:
    """Mock provider recording invocation counts and payload without network calls."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.provider_name: ProviderName = "scripted"
        self.model_name = "gpt-4o-mini"
        self.outcomes = list(outcomes)
        self.call_count = 0

    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> ProviderResponse:
        self.call_count += 1
        if not self.outcomes:
            return ProviderResponse(
                raw_text=SAMPLE_REPLY.model_dump_json(),
                input_tokens=100,
                output_tokens=50,
                model_name=self.model_name,
            )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_heuristic_counter_basic() -> None:
    counter = HeuristicCounter()
    assert counter.approximate is True
    assert counter.name == "heuristic"
    assert counter.count_text("") == 0
    assert counter.count_text("hello") == 1  # 5 // 4 = 1
    assert counter.count_text("hello world") == 2  # 11 // 4 = 2
    assert counter.count_text("a" * 100) == 25  # 100 // 4 = 25

    msgs = [{"role": "user", "content": "hello world"}]
    # "user" (4 // 4 = 1) + "hello world" (11 // 4 = 2) = 3
    assert counter.count_messages(msgs) == 3
    assert counter.count_messages([]) == 0


def test_tiktoken_counter_known_strings() -> None:
    """Verifies exact token counts against OpenAI's o200k_base tokenizer.

    Token counts were computed offline using tiktoken.get_encoding('o200k_base').encode(...)
    - '': 0 tokens
    - 'hello': 1 token ([24912])
    - 'Hello, world!': 4 tokens ([13225, 11, 2375, 0])
    - 'The quick brown fox jumps over the lazy dog.': 10 tokens
    - '{"key": "value", "nested": [1, 2, 3]}': 18 tokens
    """
    counter = TiktokenCounter(model="gpt-4o-mini")
    assert counter.approximate is False
    assert counter.name == "tiktoken"

    assert counter.count_text("") == 0
    assert counter.count_text("hello") == 1
    assert counter.count_text("Hello, world!") == 4
    assert counter.count_text("The quick brown fox jumps over the lazy dog.") == 10
    assert counter.count_text('{"key": "value", "nested": [1, 2, 3]}') == 18


def test_tiktoken_counter_unicode_and_emojis() -> None:
    """Verifies multilingual Devanagari Hindi text and emoji tokens in o200k_base.

    Computed offline:
    - 'नमस्ते दुनिया': 5 tokens ([998, 1637, 14681, 628, 64593])
    - '🤖 🚀 💻': 6 tokens ([50378, 244, 169883, 222, 74580, 119])
    """
    counter = TiktokenCounter(model="gpt-4o-mini")
    assert counter.count_text("नमस्ते दुनिया") == 5
    assert counter.count_text("🤖 🚀 💻") == 6


def test_tiktoken_counter_approximate_flag_by_provider() -> None:
    # OpenAI model: exact (approximate=False)
    counter_openai = TiktokenCounter(model="gpt-4o-mini")
    assert counter_openai.approximate is False

    # Gemini model: approximation (approximate=True)
    counter_gemini = TiktokenCounter(model="gemini-2.5-flash", provider="gemini")
    assert counter_gemini.approximate is True

    # Anthropic model: approximation (approximate=True)
    counter_claude = TiktokenCounter(model="claude-3-5-haiku-latest", provider="anthropic")
    assert counter_claude.approximate is True

    # Explicit override takes precedence
    counter_custom = TiktokenCounter(model="gpt-4o-mini", approximate=True)
    assert counter_custom.approximate is True


def test_tiktoken_count_messages_openai_overhead() -> None:
    """Verifies chat message framing overhead matching OpenAI cookbook formula.

    Formula:
    Each message adds:
      tokens_per_message (3) + sum(len(encode(val)))
    Final assistant priming:
      + 3 tokens (<|start|>assistant<|message|>)

    Case 1: [{'role': 'user', 'content': 'hello'}]
      Message overhead: 3
      'user': 1 token
      'hello': 1 token
      Priming: 3
      Total = 3 + 1 + 1 + 3 = 8 tokens

    Case 2: 2 messages (system + user) = 19 tokens
    """
    counter = TiktokenCounter(model="gpt-4o-mini")
    assert counter.count_messages([]) == 0

    msgs1 = [{"role": "user", "content": "hello"}]
    assert counter.count_messages(msgs1) == 8

    msgs2 = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]
    assert counter.count_messages(msgs2) == 19


def test_fallback_when_encoding_loader_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that if loading encoding raises, fallback to heuristic occurs and logs flag."""
    test_logger = logging.getLogger("test.tokens.fallback")
    test_logger.setLevel(logging.INFO)
    test_logger.handlers.clear()
    spy_handler = MockAuditHandler()
    test_logger.addHandler(spy_handler)

    # Monkeypatch get_audit_logger to return our test logger
    monkeypatch.setattr("chatbot.tokens.get_audit_logger", lambda: test_logger)

    def raise_load_error(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Simulated BPE vocab network download failure")

    monkeypatch.setattr("tiktoken.encoding_for_model", raise_load_error)
    monkeypatch.setattr("tiktoken.get_encoding", raise_load_error)
    # Clear process cache so load is triggered
    monkeypatch.setattr("chatbot.tokens._ENCODING_CACHE", {})

    # Instantiate counter and invoke counting
    counter = TiktokenCounter(model="unseen-model-fail")
    count = counter.count_text("hello world")

    # Degrades gracefully to heuristic: len("hello world") // 4 = 11 // 4 = 2
    assert count == 2
    assert counter.approximate is True

    # Audit log must have recorded token_counter_fallback flag
    assert len(spy_handler.records) >= 1
    fallback_records = [
        r
        for r in spy_handler.records
        if hasattr(r, "metadata")
        and isinstance(r.metadata, dict)
        and r.metadata.get("token_counter_fallback") is True
    ]
    assert len(fallback_records) >= 1
    assert fallback_records[0].metadata["error_code"] == "RuntimeError"


def test_get_counter_factory_and_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Heuristic mode via argument
    h_counter = get_counter(mode="heuristic")
    assert isinstance(h_counter, HeuristicCounter)

    # Heuristic mode via env var
    monkeypatch.setenv("TOKEN_COUNTER", "heuristic")
    env_h_counter = get_counter()
    assert isinstance(env_h_counter, HeuristicCounter)

    # Tiktoken default mode
    monkeypatch.setenv("TOKEN_COUNTER", "tiktoken")
    t_counter = get_counter(model="gpt-4o-mini")
    assert isinstance(t_counter, TiktokenCounter)
    assert t_counter.approximate is False


def test_memory_eviction_with_tiktoken_counter() -> None:
    """Verifies sliding-window memory evicts turns based on TiktokenCounter counts."""
    tiktoken_counter = TiktokenCounter(model="gpt-4o-mini")
    # Set max_estimated_tokens small enough that 2 turns fit but 3 exceed (min bound is 100)
    mem = ConversationMemory(max_turns=10, max_estimated_tokens=120, counter=tiktoken_counter)

    # Turn 1
    rep1 = StructuredReply(
        answer="Short answer 1",
        category="general",
        key_points=["Point 1"],
        follow_up_questions=["Next?"],
        confidence=0.9,
    )
    mem.add_turn(UserTurnInput(text="Q1"), rep1, turn_id="TURN-0001")
    tokens_t1 = mem.estimated_tokens
    assert mem.turn_count == 1
    assert tokens_t1 > 0

    # Turn 2
    rep2 = StructuredReply(
        answer="Short answer 2",
        category="general",
        key_points=["Point 2"],
        follow_up_questions=["Next 2?"],
        confidence=0.9,
    )
    mem.add_turn(UserTurnInput(text="Q2"), rep2, turn_id="TURN-0002")
    assert mem.turn_count == 2
    tokens_t2 = mem.estimated_tokens
    assert tokens_t2 > tokens_t1

    # Turn 3 with larger text to exceed 80 tokens
    rep3 = StructuredReply(
        answer="A much longer technical explanation with significant detail " * 3,
        category="technical",
        key_points=["Detailed point A", "Detailed point B"],
        follow_up_questions=["In-depth follow up question?"],
        confidence=0.9,
    )
    mem.add_turn(UserTurnInput(text="Q3"), rep3, turn_id="TURN-0003")

    # Oldest turn (TURN-0001) should have been evicted to keep total <= 120
    assert mem.estimated_tokens <= 120
    stored_ids = [t.turn_id for t in mem.turns]
    assert "TURN-0001" not in stored_ids
    assert "TURN-0003" in stored_ids

    # Test recount method
    mem.recount()
    assert mem.estimated_tokens <= 120


def test_budget_precheck_blocks_before_provider_is_called() -> None:
    """Verifies budget pre-check raises BudgetExceededError before calling provider."""
    # Response prepared in queue
    fake_response = ProviderResponse(
        raw_text=SAMPLE_REPLY.model_dump_json(),
        input_tokens=50,
        output_tokens=30,
        model_name="gpt-4o-mini",
    )
    provider = SpyQueueProvider([fake_response])
    router = ResilientRouter(providers=[provider])

    # Very small budget ($0.0000001) which cannot cover the input tokens
    tracker = CostTracker(session_budget_usd=0.0000001)
    orchestrator = ChatOrchestrator(
        router=router,
        cost_tracker=tracker,
        token_counter=TiktokenCounter(model="gpt-4o-mini"),
    )

    with pytest.raises(BudgetExceededError) as exc_info:
        orchestrator.turn(UserTurnInput(text="Explain database indexing in full detail"))

    # Crucial assertion: provider was NEVER invoked
    assert provider.call_count == 0
    assert "projected input cost" in str(exc_info.value)
    # Tracker cumulative spend was not incremented
    assert tracker.total_turns == 0
    assert tracker.total_cost_usd == 0.0
