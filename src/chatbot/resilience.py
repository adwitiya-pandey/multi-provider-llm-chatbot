"""Exponential backoff retry and automatic multi-provider fallback engine (SPEC 5)."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from chatbot.models import ProviderAttempt, ProviderName
from chatbot.providers import LLMProvider, ProviderError, ProviderResponse


class AllProvidersFailedError(Exception):
    """Raised when all configured providers in the fallback chain fail."""

    def __init__(self, attempts: list[ProviderAttempt]) -> None:
        failed_attempts = [a for a in attempts if not a.success]
        summary = ", ".join(f"{a.provider}:{a.error_code or 'UNKNOWN'}" for a in failed_attempts)
        super().__init__(f"All configured providers failed: [{summary}]")
        self.attempts = attempts


@dataclass
class RouterResult:
    """Outcome of a resilient multi-provider routing request."""

    response: ProviderResponse
    provider_used: ProviderName
    model_used: str
    retries_used: int
    fallback_used: bool
    attempts: list[ProviderAttempt] = field(default_factory=list)


class ResilientRouter:
    """Dispatches generation requests with exponential backoff and automatic provider fallback."""

    def __init__(
        self,
        providers: list[LLMProvider],
        max_retries: int = 3,
        base_delay: float = 1.0,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if not providers:
            raise ValueError("ResilientRouter requires at least one provider")

        self.providers = providers
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.sleep_fn = sleep_fn

    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> RouterResult:
        """Executes generation across the provider chain with retry and fallback."""
        all_attempts: list[ProviderAttempt] = []
        total_retries_used = 0
        overall_attempt_number = 0

        for provider_idx, provider in enumerate(self.providers):
            provider_retries = 0
            fallback_active = provider_idx > 0

            for attempt_idx in range(1 + self.max_retries):
                overall_attempt_number += 1
                start_time = time.perf_counter()

                try:
                    response = provider.generate(system_prompt, messages)
                    latency_ms = (time.perf_counter() - start_time) * 1000.0

                    all_attempts.append(
                        ProviderAttempt(
                            provider=provider.provider_name,
                            model=provider.model_name,
                            attempt_number=overall_attempt_number,
                            success=True,
                            error_code=None,
                            latency_ms=round(latency_ms, 2),
                        )
                    )

                    return RouterResult(
                        response=response,
                        provider_used=provider.provider_name,
                        model_used=provider.model_name,
                        retries_used=total_retries_used,
                        fallback_used=fallback_active,
                        attempts=all_attempts,
                    )
                except ProviderError as exc:
                    latency_ms = (time.perf_counter() - start_time) * 1000.0

                    all_attempts.append(
                        ProviderAttempt(
                            provider=provider.provider_name,
                            model=provider.model_name,
                            attempt_number=overall_attempt_number,
                            success=False,
                            error_code=exc.code,
                            latency_ms=round(latency_ms, 2),
                        )
                    )

                    # Check if retryable and attempts remain on this provider
                    can_retry = exc.retryable and (provider_retries < self.max_retries)

                    if can_retry:
                        delay = self.base_delay * (2**provider_retries)
                        self.sleep_fn(delay)
                        provider_retries += 1
                        total_retries_used += 1
                    else:
                        # Non-retryable error or retries exhausted on this provider
                        # Break to advance to the next fallback provider
                        break

        # All providers exhausted without success
        raise AllProvidersFailedError(attempts=all_attempts)
