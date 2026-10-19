"""Unit tests for multi-provider SDK adapters using offline mock/fake clients (SPEC 4, S8)."""

from types import SimpleNamespace
from typing import Any

import anthropic
import openai
import pytest
from google.genai import errors as genai_errors

from chatbot.models import StructuredReply
from chatbot.providers import (
    AnthropicProvider,
    GeminiProvider,
    OpenAIProvider,
    ProviderError,
    ScriptedProvider,
)

SAMPLE_JSON = StructuredReply(
    answer="Normalized test response",
    category="technical",
    key_points=["Point 1", "Point 2"],
    follow_up_questions=["Question 1?"],
    confidence=0.99,
).model_dump_json()


# ==============================================================================
# FAKE SDK CLIENTS
# ==============================================================================


class FakeGeminiModels:
    def __init__(self, side_effect: Any = None) -> None:
        self.side_effect = side_effect
        self.last_call: dict[str, Any] = {}

    def generate_content(self, model: str, contents: Any, config: Any) -> Any:
        self.last_call = {"model": model, "contents": contents, "config": config}
        if isinstance(self.side_effect, Exception):
            raise self.side_effect
        if callable(self.side_effect):
            return self.side_effect(model, contents, config)

        usage = SimpleNamespace(prompt_token_count=150, candidates_token_count=75)
        return SimpleNamespace(text=SAMPLE_JSON, usage_metadata=usage)


class FakeGeminiClient:
    def __init__(self, side_effect: Any = None) -> None:
        self.models = FakeGeminiModels(side_effect)


class FakeAnthropicMessages:
    def __init__(self, side_effect: Any = None) -> None:
        self.side_effect = side_effect
        self.last_call: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.last_call = kwargs
        if isinstance(self.side_effect, Exception):
            raise self.side_effect
        if callable(self.side_effect):
            return self.side_effect(**kwargs)

        usage = SimpleNamespace(input_tokens=140, output_tokens=70)
        content_item = SimpleNamespace(text=SAMPLE_JSON)
        return SimpleNamespace(content=[content_item], usage=usage)


class FakeAnthropicClient:
    def __init__(self, side_effect: Any = None) -> None:
        self.messages = FakeAnthropicMessages(side_effect)


class FakeOpenAIChatCompletions:
    def __init__(self, side_effect: Any = None) -> None:
        self.side_effect = side_effect
        self.last_call: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.last_call = kwargs
        if isinstance(self.side_effect, Exception):
            raise self.side_effect
        if callable(self.side_effect):
            return self.side_effect(**kwargs)

        usage = SimpleNamespace(prompt_tokens=130, completion_tokens=65)
        choice = SimpleNamespace(message=SimpleNamespace(content=SAMPLE_JSON))
        return SimpleNamespace(choices=[choice], usage=usage)


class FakeOpenAIClient:
    def __init__(self, side_effect: Any = None) -> None:
        self.chat = SimpleNamespace(completions=FakeOpenAIChatCompletions(side_effect))


# ==============================================================================
# GEMINI PROVIDER TESTS
# ==============================================================================


def test_gemini_provider_success() -> None:
    fake_client = FakeGeminiClient()
    provider = GeminiProvider(
        model_name="gemini-2.5-flash",
        sdk_client=fake_client,
    )
    resp = provider.generate("System prompt", [{"role": "user", "content": "Hello"}])

    assert resp.model_name == "gemini-2.5-flash"
    assert resp.input_tokens == 150
    assert resp.output_tokens == 75
    assert resp.raw_text == SAMPLE_JSON
    assert fake_client.models.last_call["model"] == "gemini-2.5-flash"


def test_gemini_provider_rate_limit_mapping() -> None:
    # 429 APIError is retryable
    exc = genai_errors.APIError(429, {"message": "Resource exhausted"})
    fake_client = FakeGeminiClient(side_effect=exc)
    provider = GeminiProvider(sdk_client=fake_client)

    with pytest.raises(ProviderError) as exc_info:
        provider.generate("System", [{"role": "user", "content": "Hello"}])

    assert exc_info.value.code == "RATE_LIMITED"
    assert exc_info.value.retryable is True
    assert exc_info.value.provider == "gemini"


def test_gemini_provider_server_error_mapping() -> None:
    exc = genai_errors.APIError(503, {"message": "Service Unavailable"})
    fake_client = FakeGeminiClient(side_effect=exc)
    provider = GeminiProvider(sdk_client=fake_client)

    with pytest.raises(ProviderError) as exc_info:
        provider.generate("System", [{"role": "user", "content": "Hello"}])

    assert exc_info.value.code == "SERVER_ERROR"
    assert exc_info.value.retryable is True


def test_gemini_provider_auth_error_mapping() -> None:
    exc = genai_errors.APIError(401, {"message": "Unauthorized"})
    fake_client = FakeGeminiClient(side_effect=exc)
    provider = GeminiProvider(sdk_client=fake_client)

    with pytest.raises(ProviderError) as exc_info:
        provider.generate("System", [{"role": "user", "content": "Hello"}])

    assert exc_info.value.code == "AUTH_ERROR"
    assert exc_info.value.retryable is False


def test_gemini_missing_key_error() -> None:
    with pytest.raises(ProviderError) as exc_info:
        GeminiProvider(api_key=None, sdk_client=None)

    assert exc_info.value.code == "MISSING_KEY"
    assert exc_info.value.retryable is False


# ==============================================================================
# ANTHROPIC PROVIDER TESTS
# ==============================================================================


def test_anthropic_provider_success() -> None:
    fake_client = FakeAnthropicClient()
    provider = AnthropicProvider(
        model_name="claude-3-5-haiku-latest",
        sdk_client=fake_client,
    )
    resp = provider.generate("System prompt", [{"role": "user", "content": "Hello"}])

    assert resp.model_name == "claude-3-5-haiku-latest"
    assert resp.input_tokens == 140
    assert resp.output_tokens == 70
    assert resp.raw_text == SAMPLE_JSON
    assert fake_client.messages.last_call["model"] == "claude-3-5-haiku-latest"


def test_anthropic_provider_rate_limit_mapping() -> None:
    # Construct mock rate limit error
    request = SimpleNamespace(headers={})
    exc = anthropic.RateLimitError(
        message="Rate limit exceeded",
        response=SimpleNamespace(
            status_code=429, headers={}, request=request, is_closed=True, close=lambda: None
        ),  # type: ignore[arg-type]
        body=None,
    )
    fake_client = FakeAnthropicClient(side_effect=exc)
    provider = AnthropicProvider(sdk_client=fake_client)

    with pytest.raises(ProviderError) as exc_info:
        provider.generate("System", [{"role": "user", "content": "Hello"}])

    assert exc_info.value.code == "RATE_LIMITED"
    assert exc_info.value.retryable is True
    assert exc_info.value.provider == "anthropic"


def test_anthropic_provider_auth_error_mapping() -> None:
    request = SimpleNamespace(headers={})
    exc = anthropic.AuthenticationError(
        message="Invalid API Key",
        response=SimpleNamespace(
            status_code=401, headers={}, request=request, is_closed=True, close=lambda: None
        ),  # type: ignore[arg-type]
        body=None,
    )
    fake_client = FakeAnthropicClient(side_effect=exc)
    provider = AnthropicProvider(sdk_client=fake_client)

    with pytest.raises(ProviderError) as exc_info:
        provider.generate("System", [{"role": "user", "content": "Hello"}])

    assert exc_info.value.code == "AUTH_ERROR"
    assert exc_info.value.retryable is False


def test_anthropic_missing_key_error() -> None:
    with pytest.raises(ProviderError) as exc_info:
        AnthropicProvider(api_key=None, sdk_client=None)

    assert exc_info.value.code == "MISSING_KEY"
    assert exc_info.value.retryable is False


# ==============================================================================
# OPENAI PROVIDER TESTS
# ==============================================================================


def test_openai_provider_success() -> None:
    fake_client = FakeOpenAIClient()
    provider = OpenAIProvider(
        model_name="gpt-4o-mini",
        sdk_client=fake_client,
    )
    resp = provider.generate("System prompt", [{"role": "user", "content": "Hello"}])

    assert resp.model_name == "gpt-4o-mini"
    assert resp.input_tokens == 130
    assert resp.output_tokens == 65
    assert resp.raw_text == SAMPLE_JSON
    assert fake_client.chat.completions.last_call["model"] == "gpt-4o-mini"


def test_openai_provider_rate_limit_mapping() -> None:
    request = SimpleNamespace(headers={})
    exc = openai.RateLimitError(
        message="Rate limit exceeded",
        response=SimpleNamespace(
            status_code=429, headers={}, request=request, is_closed=True, close=lambda: None
        ),  # type: ignore[arg-type]
        body=None,
    )
    fake_client = FakeOpenAIClient(side_effect=exc)
    provider = OpenAIProvider(sdk_client=fake_client)

    with pytest.raises(ProviderError) as exc_info:
        provider.generate("System", [{"role": "user", "content": "Hello"}])

    assert exc_info.value.code == "RATE_LIMITED"
    assert exc_info.value.retryable is True
    assert exc_info.value.provider == "openai"


def test_openai_provider_auth_error_mapping() -> None:
    request = SimpleNamespace(headers={})
    exc = openai.AuthenticationError(
        message="Incorrect API key provided",
        response=SimpleNamespace(
            status_code=401, headers={}, request=request, is_closed=True, close=lambda: None
        ),  # type: ignore[arg-type]
        body=None,
    )
    fake_client = FakeOpenAIClient(side_effect=exc)
    provider = OpenAIProvider(sdk_client=fake_client)

    with pytest.raises(ProviderError) as exc_info:
        provider.generate("System", [{"role": "user", "content": "Hello"}])

    assert exc_info.value.code == "AUTH_ERROR"
    assert exc_info.value.retryable is False


def test_openai_missing_key_error() -> None:
    with pytest.raises(ProviderError) as exc_info:
        OpenAIProvider(api_key=None, sdk_client=None)

    assert exc_info.value.code == "MISSING_KEY"
    assert exc_info.value.retryable is False


# ==============================================================================
# SCRIPTED PROVIDER TESTS
# ==============================================================================


def test_scripted_provider_success() -> None:
    provider = ScriptedProvider()
    resp = provider.generate(
        "System prompt",
        [{"role": "user", "content": "Tell me about rate limiting 429"}],
    )
    assert resp.input_tokens == 120
    assert resp.output_tokens == 85
    assert "429" in resp.raw_text or "rate limiting" in resp.raw_text.lower()
    parsed = StructuredReply.model_validate_json(resp.raw_text)
    assert parsed.category == "technical"
    assert len(parsed.key_points) >= 1


def test_scripted_provider_force_error() -> None:
    forced = ProviderError(code="SERVER_ERROR", provider="scripted", retryable=True)
    provider = ScriptedProvider(force_error=forced)

    with pytest.raises(ProviderError) as exc_info:
        provider.generate("System", [{"role": "user", "content": "Hello"}])

    assert exc_info.value.code == "SERVER_ERROR"
    assert exc_info.value.retryable is True
