"""Strict Pydantic data models for multi-provider LLM chatbot."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProviderName = Literal["gemini", "anthropic", "openai", "scripted"]
Role = Literal["user", "assistant"]
CategoryName = Literal["general", "technical", "clarification", "refusal"]


class ChatMessage(BaseModel):
    """Represents a single message in the conversation history."""

    model_config = ConfigDict(extra="forbid", strict=True)

    role: Role
    content: str = Field(min_length=1, max_length=12000)
    turn_id: str = Field(pattern=r"^TURN-[0-9]{4}$")


class UserTurnInput(BaseModel):
    """User input for a single conversation turn."""

    model_config = ConfigDict(extra="forbid", strict=True)

    text: str = Field(min_length=1, max_length=4000)
    domain_focus: str = Field(default="General AI & Data Engineering", min_length=2, max_length=100)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class StructuredReply(BaseModel):
    """Normalized structured JSON response required from all providers."""

    model_config = ConfigDict(extra="forbid", strict=True)

    answer: str = Field(min_length=1, max_length=4000)
    category: CategoryName
    key_points: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(
        min_length=1, max_length=5
    )
    follow_up_questions: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        min_length=1, max_length=3
    )
    confidence: float = Field(ge=0.0, le=1.0)


class UsageStats(BaseModel):
    """Token consumption and USD cost accounting."""

    model_config = ConfigDict(extra="forbid", strict=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)


class ProviderAttempt(BaseModel):
    """Record of a single attempt to call an LLM provider."""

    model_config = ConfigDict(extra="forbid", strict=True)

    provider: ProviderName
    model: str = Field(min_length=1)
    attempt_number: int = Field(ge=1)
    success: bool
    error_code: str | None = None
    latency_ms: float = Field(ge=0.0)


class TurnResult(BaseModel):
    """Comprehensive outcome of a full chat interaction turn."""

    model_config = ConfigDict(extra="forbid", strict=True)

    turn_id: str = Field(pattern=r"^TURN-[0-9]{4}$")
    reply: StructuredReply
    provider_used: ProviderName
    model_used: str = Field(min_length=1)
    retries_used: int = Field(ge=0)
    fallback_used: bool
    repair_used: bool
    injection_flagged: bool
    usage: UsageStats
    attempts: list[ProviderAttempt]
