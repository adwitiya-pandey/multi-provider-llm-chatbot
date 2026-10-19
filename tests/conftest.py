"""Pytest configuration and test isolation fixtures."""

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Ensure all unit tests run in offline isolation with zero real keys by default."""
    # Remove real ambient keys so unit tests do not accidentally contact real provider APIs
    for key in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LLM_MODE", "scripted")
    yield
