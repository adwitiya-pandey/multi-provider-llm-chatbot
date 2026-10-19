"""Unit tests for exponential backoff and automatic provider fallback (SPEC 5, Gotcha 4)."""

from typing import Any

import pytest

from chatbot.models import ProviderName
from chatbot.providers import ProviderError, ProviderResponse
from chatbot.resilience import AllProvidersFailedError, ResilientRouter


class MockProvider:
    """Mock provider allowing queued sequence of errors and responses."""

    def __init__(
        self,
        name: ProviderName,
        model: str,
        outcomes: list[Any],
    ) -> None:
        self.provider_name: ProviderName = name
        self.model_name = model
        self.outcomes = list(outcomes)
        self.calls_count = 0

    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> ProviderResponse:
        self.calls_count += 1
        if not self.outcomes:
            return ProviderResponse(
                raw_text="{}",
                input_tokens=10,
                output_tokens=10,
                model_name=self.model_name,
            )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _make_success_response(model: str = "test-model") -> ProviderResponse:
    return ProviderResponse(
        raw_text='{"answer": "ok"}',
        input_tokens=100,
        output_tokens=50,
        model_name=model,
    )


def test_primary_succeeds_first_attempt() -> None:
    sleeps: list[float] = []
    primary = MockProvider("gemini", "gemini-2.5-flash", [_make_success_response()])
    router = ResilientRouter(providers=[primary], sleep_fn=sleeps.append)

    result = router.generate("System", [{"role": "user", "content": "Hi"}])

    assert result.provider_used == "gemini"
    assert result.model_used == "gemini-2.5-flash"
    assert result.retries_used == 0
    assert not result.fallback_used
    assert sleeps == []
    assert len(result.attempts) == 1
    assert result.attempts[0].success is True


def test_primary_fails_twice_429_then_succeeds() -> None:
    sleeps: list[float] = []
    err1 = ProviderError(code="RATE_LIMITED", provider="gemini", retryable=True)
    err2 = ProviderError(code="RATE_LIMITED", provider="gemini", retryable=True)
    succ = _make_success_response("gemini-2.5-flash")

    primary = MockProvider("gemini", "gemini-2.5-flash", [err1, err2, succ])
    router = ResilientRouter(providers=[primary], sleep_fn=sleeps.append)

    result = router.generate("System", [{"role": "user", "content": "Hi"}])

    assert result.provider_used == "gemini"
    assert result.retries_used == 2
    assert not result.fallback_used
    assert sleeps == [1.0, 2.0]
    assert len(result.attempts) == 3
    assert not result.attempts[0].success
    assert not result.attempts[1].success
    assert result.attempts[2].success


def test_primary_fails_4_times_503_fallback_to_secondary_succeeds() -> None:
    sleeps: list[float] = []
    # 4 consecutive 503 errors on primary (1 initial + 3 retries)
    p_errors = [
        ProviderError(code="SERVER_ERROR", provider="gemini", retryable=True) for _ in range(4)
    ]
    primary = MockProvider("gemini", "gemini-2.5-flash", p_errors)
    secondary = MockProvider(
        "gemini", "gemini-2.5-flash-lite", [_make_success_response("gemini-2.5-flash-lite")]
    )

    router = ResilientRouter(
        providers=[primary, secondary],
        max_retries=3,
        base_delay=1.0,
        sleep_fn=sleeps.append,
    )

    result = router.generate("System", [{"role": "user", "content": "Hi"}])

    assert result.provider_used == "gemini"
    assert result.model_used == "gemini-2.5-flash-lite"
    assert result.fallback_used is True
    assert sleeps == [1.0, 2.0, 4.0]
    assert len(result.attempts) == 5  # 4 on primary, 1 on secondary
    assert result.attempts[4].success is True


def test_primary_auth_error_immediate_fallback_zero_retries() -> None:
    sleeps: list[float] = []
    # 401 AUTH_ERROR is non-retryable
    auth_err = ProviderError(code="AUTH_ERROR", provider="gemini", retryable=False)
    primary = MockProvider("gemini", "gemini-2.5-flash", [auth_err])
    secondary = MockProvider("scripted", "scripted-demo", [_make_success_response("scripted-demo")])

    router = ResilientRouter(
        providers=[primary, secondary],
        sleep_fn=sleeps.append,
    )

    result = router.generate("System", [{"role": "user", "content": "Hi"}])

    assert result.provider_used == "scripted"
    assert result.model_used == "scripted-demo"
    assert result.fallback_used is True
    assert result.retries_used == 0
    assert sleeps == []  # No retry sleeps on 401!
    assert len(result.attempts) == 2


def test_all_providers_fail_raises_typed_error() -> None:
    sleeps: list[float] = []
    err1 = ProviderError(code="AUTH_ERROR", provider="gemini", retryable=False)
    err2 = ProviderError(code="SERVER_ERROR", provider="anthropic", retryable=False)

    p1 = MockProvider("gemini", "gemini-2.5-flash", [err1])
    p2 = MockProvider("anthropic", "claude-3-5-haiku-latest", [err2])

    router = ResilientRouter(providers=[p1, p2], sleep_fn=sleeps.append)

    with pytest.raises(AllProvidersFailedError) as exc_info:
        router.generate("System", [{"role": "user", "content": "Hi"}])

    msg = str(exc_info.value)
    assert "gemini:AUTH_ERROR" in msg
    assert "anthropic:SERVER_ERROR" in msg
    assert len(exc_info.value.attempts) == 2


def test_router_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="at least one provider"):
        ResilientRouter(providers=[])
