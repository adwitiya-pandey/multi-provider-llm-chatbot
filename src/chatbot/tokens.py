"""Token counting implementations: TokenCounter protocol, HeuristicCounter, and TiktokenCounter."""

import logging
import os
from typing import Any, Protocol, runtime_checkable

import tiktoken

from chatbot.config import get_settings
from chatbot.logging_setup import get_audit_logger, log_turn_event

logger = logging.getLogger(__name__)

# Process-level cache for tiktoken encodings
_ENCODING_CACHE: dict[str, Any] = {}


def _get_cached_encoding(model: str) -> Any:
    """Loads and caches a tiktoken encoding for the given model or falls back to o200k_base."""
    if model in _ENCODING_CACHE:
        return _ENCODING_CACHE[model]

    # Ensure TIKTOKEN_CACHE_DIR from settings is reflected in os.environ if configured
    try:
        settings = get_settings()
        if settings.TIKTOKEN_CACHE_DIR and "TIKTOKEN_CACHE_DIR" not in os.environ:
            os.environ["TIKTOKEN_CACHE_DIR"] = settings.TIKTOKEN_CACHE_DIR
    except Exception:
        pass

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Model not directly mapped in tiktoken (e.g., Gemini or Claude); default to o200k_base
        encoding = tiktoken.get_encoding("o200k_base")

    _ENCODING_CACHE[model] = encoding
    return encoding


@runtime_checkable
class TokenCounter(Protocol):
    """Protocol defining the interface for token counting implementations."""

    approximate: bool
    name: str

    def count_text(self, text: str) -> int:
        """Counts tokens in a plain text string."""
        ...

    def count_messages(self, messages: list[dict[str, str]]) -> int:
        """Counts tokens in a list of chat message dictionaries."""
        ...


class HeuristicCounter:
    """Heuristic token counter using standard character-length estimation (len // 4)."""

    def __init__(self) -> None:
        self.approximate: bool = True
        self.name: str = "heuristic"

    def count_text(self, text: str) -> int:
        """Conservatively estimates tokens as max(1, len(text) // 4), or 0 if text is empty."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def count_messages(self, messages: list[dict[str, str]]) -> int:
        """Estimates tokens across a list of message dictionaries."""
        if not messages:
            return 0
        total = 0
        for msg in messages:
            for val in msg.values():
                total += self.count_text(val)
        return total


class TiktokenCounter:
    """BPE token counter powered by OpenAI's tiktoken library."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        provider: str | None = None,
        approximate: bool | None = None,
    ) -> None:
        self.model = model
        self.provider = provider
        self.name: str = "tiktoken"

        if approximate is not None:
            self.approximate = approximate
        else:
            self.approximate = not self._is_openai_model(model, provider)

        self._encoding: Any = None
        self._fallback_counter: HeuristicCounter | None = None

    @staticmethod
    def _is_openai_model(model: str, provider: str | None = None) -> bool:
        """Returns True if the model belongs to OpenAI, False for any other provider."""
        if provider is not None:
            p = provider.lower()
            if p == "openai":
                return True
            if p in {"gemini", "google", "anthropic", "scripted"}:
                return False
        lower_m = model.lower()
        return lower_m.startswith(("gpt-", "o1", "o3", "text-embedding", "chatgpt", "dall-e"))

    def _get_encoding(self) -> Any:
        """Lazily loads the tiktoken encoding with graceful fallback to HeuristicCounter."""
        if self._encoding is not None:
            return self._encoding
        if self._fallback_counter is not None:
            return None

        try:
            self._encoding = _get_cached_encoding(self.model)
            return self._encoding
        except Exception as exc:
            # Log token_counter_fallback and degrade gracefully
            audit_logger = get_audit_logger()
            log_turn_event(
                audit_logger,
                {
                    "status": "warning",
                    "token_counter_fallback": True,
                    "error_code": type(exc).__name__,
                },
            )
            self._fallback_counter = HeuristicCounter()
            self.approximate = True
            return None

    def count_text(self, text: str) -> int:
        """Counts tokens in a plain text string."""
        if not text:
            return 0
        encoding = self._get_encoding()
        if encoding is not None:
            return len(encoding.encode(text))
        assert self._fallback_counter is not None
        return self._fallback_counter.count_text(text)

    def count_messages(self, messages: list[dict[str, str]]) -> int:
        """Counts tokens in chat format messages including OpenAI framing overhead.

        Follows OpenAI Cookbook formula for chat models:
        https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        """
        if not messages:
            return 0
        encoding = self._get_encoding()
        if encoding is None:
            assert self._fallback_counter is not None
            return self._fallback_counter.count_messages(messages)

        # Standard chat completion message overhead (gpt-4o / gpt-4o-mini / gpt-4)
        # Citing OpenAI Cookbook:
        # "Every message follows <|start|>{role/name}\n{content}<|end|>\n"
        tokens_per_message = 3
        tokens_per_name = 1
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # Every reply is primed with <|start|>assistant<|message|>
        return num_tokens


def get_counter(
    provider: str | None = None,
    model: str | None = None,
    mode: str | None = None,
) -> TokenCounter:
    """Factory returning TokenCounter based on mode, provider, and model.

    Mode is determined from mode argument, or TOKEN_COUNTER env var ('tiktoken' or 'heuristic').
    """
    resolved_mode = (mode or os.environ.get("TOKEN_COUNTER", "tiktoken")).lower().strip()
    if resolved_mode == "heuristic":
        return HeuristicCounter()

    target_model = model or "gpt-4o-mini"
    counter = TiktokenCounter(model=target_model, provider=provider)
    # Pre-test loading to verify if fallback is triggered immediately
    try:
        enc = counter._get_encoding()
        if enc is None and counter._fallback_counter is not None:
            return counter._fallback_counter
    except Exception as exc:
        audit_logger = get_audit_logger()
        log_turn_event(
            audit_logger,
            {
                "status": "warning",
                "token_counter_fallback": True,
                "error_code": type(exc).__name__,
            },
        )
        return HeuristicCounter()

    return counter
