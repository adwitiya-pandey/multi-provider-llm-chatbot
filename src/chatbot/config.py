"""Application configuration loaded from environment and local .env."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Chatbot settings with automatic mode resolution and secret masking."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys (Loaded securely as SecretStr)
    GEMINI_API_KEY: SecretStr | None = Field(default=None)
    ANTHROPIC_API_KEY: SecretStr | None = Field(default=None)
    OPENAI_API_KEY: SecretStr | None = Field(default=None)

    # Execution Mode: "auto", "live", or "scripted"
    LLM_MODE: Literal["auto", "live", "scripted"] = Field(default="auto")

    # Financial and Memory Guardrails
    SESSION_BUDGET_USD: float = Field(default=0.50, ge=0.01, le=100.0)
    MAX_HISTORY_TURNS: int = Field(default=10, ge=1, le=100)
    MAX_HISTORY_TOKENS: int = Field(default=6000, ge=100, le=100000)

    # Model IDs
    PRIMARY_MODEL_GEMINI: str = Field(default="gemini-3.8-flash")
    FALLBACK_MODEL_GEMINI: str = Field(default="gemini-3.5-flash-lite")
    MODEL_ANTHROPIC: str = Field(default="claude-3-5-haiku-latest")
    MODEL_OPENAI: str = Field(default="gpt-4o-mini")

    @property
    def resolved_mode(self) -> Literal["live", "scripted"]:
        """Resolves active LLM mode based on configuration and available keys.

        - If LLM_MODE is 'scripted', returns 'scripted'.
        - If LLM_MODE is 'live', returns 'live'.
        - If LLM_MODE is 'auto', returns 'live' if GEMINI_API_KEY is present and non-empty,
          otherwise gracefully defaults to 'scripted'.
        """
        if self.LLM_MODE == "scripted":
            return "scripted"
        if self.LLM_MODE == "live":
            return "live"

        # auto mode
        if self.GEMINI_API_KEY is not None and bool(self.GEMINI_API_KEY.get_secret_value().strip()):
            return "live"
        return "scripted"

    def has_gemini_key(self) -> bool:
        """Returns True if a non-empty GEMINI_API_KEY is configured."""
        return self.GEMINI_API_KEY is not None and bool(
            self.GEMINI_API_KEY.get_secret_value().strip()
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns cached application settings instance."""
    return Settings()
