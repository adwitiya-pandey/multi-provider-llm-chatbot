"""Security verification suite covering S1–S8 requirements."""

import os
from pathlib import Path

from pydantic import SecretStr

from chatbot.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_s1_gitignore_covers_env() -> None:
    """S1: Verify .gitignore explicitly excludes .env and secret patterns."""
    gitignore = REPO_ROOT / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines()]

    assert ".env" in lines
    assert ".env.*" in lines
    assert "!.env.example" in lines


def test_s1_env_example_has_no_real_keys() -> None:
    """S1: Verify .env.example contains only non-secret placeholders."""
    env_example = REPO_ROOT / ".env.example"
    assert env_example.exists()
    content = env_example.read_text(encoding="utf-8")

    # Real Gemini keys typically start with AIzaSy
    # Real Anthropic keys start with sk-ant-
    # Real OpenAI keys start with sk-proj- or sk-
    assert "AIzaSy" not in content
    assert "sk-ant-" not in content
    assert "sk-proj-" not in content
    assert "your-gemini-key-here" in content


def test_s1_config_never_exposes_secret_in_str_or_repr() -> None:
    """S1: Verify SecretStr never exposes the real key in representations."""
    raw_secret = "AIzaSyFakeSecretKeyThatMustNeverLeak1234"
    settings = Settings(
        _env_file=None,
        GEMINI_API_KEY=SecretStr(raw_secret),
    )

    str_repr = str(settings)
    assert raw_secret not in str_repr
    assert raw_secret not in repr(settings)
    assert raw_secret not in str(settings.GEMINI_API_KEY)
    assert repr(settings.GEMINI_API_KEY) == "SecretStr('**********')"


def test_s8_ambient_keys_not_in_test_env() -> None:
    """S8: Verify tests conftest correctly cleared ambient live API keys."""
    # Under test runner, isolate_env fixture guarantees this is None/unset
    assert os.getenv("GEMINI_API_KEY") is None
    assert os.getenv("ANTHROPIC_API_KEY") is None
    assert os.getenv("OPENAI_API_KEY") is None
