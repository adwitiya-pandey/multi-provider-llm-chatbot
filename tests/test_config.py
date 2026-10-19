"""Unit tests for configuration loader and mode resolution."""

import pytest
from pydantic import ValidationError

from chatbot.config import Settings


def test_default_config_resolves_to_scripted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODE", raising=False)
    settings = Settings(_env_file=None)
    assert settings.resolved_mode == "scripted"
    assert not settings.has_gemini_key()


def test_auto_mode_with_gemini_key_resolves_to_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key-12345")
    monkeypatch.setenv("LLM_MODE", "auto")
    settings = Settings(_env_file=None)
    assert settings.resolved_mode == "live"
    assert settings.has_gemini_key()
    # Ensure SecretStr masks the secret in repr and str
    assert "fake-gemini-key-12345" not in str(settings.GEMINI_API_KEY)
    assert settings.GEMINI_API_KEY.get_secret_value() == "fake-gemini-key-12345"


def test_explicit_scripted_overrides_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key-12345")
    monkeypatch.setenv("LLM_MODE", "scripted")
    settings = Settings(_env_file=None)
    assert settings.resolved_mode == "scripted"
    assert settings.has_gemini_key()


def test_explicit_live_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_MODE", "live")
    settings = Settings(_env_file=None)
    assert settings.resolved_mode == "live"


def test_invalid_session_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SESSION_BUDGET_USD=-1.0)
