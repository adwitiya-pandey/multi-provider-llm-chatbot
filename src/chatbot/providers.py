"""Multi-provider SDK adapters for Google GenAI, Anthropic, OpenAI, and Scripted demo."""

from typing import Any, Protocol

import anthropic
import openai
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel, ConfigDict, Field

from chatbot.models import ProviderName, StructuredReply


class ProviderResponse(BaseModel):
    """Normalized output from any provider adapter."""

    model_config = ConfigDict(extra="forbid", strict=True)

    raw_text: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model_name: str


class ProviderError(Exception):
    """Normalized provider exception across SDKs."""

    def __init__(
        self,
        code: str,
        provider: ProviderName,
        retryable: bool,
        message: str = "",
        original_exception: Exception | None = None,
    ) -> None:
        super().__init__(f"[{provider}:{code}] {message}" if message else f"[{provider}:{code}]")
        self.code = code
        self.provider = provider
        self.retryable = retryable
        self.message = message
        self.original_exception = original_exception


class LLMProvider(Protocol):
    """Protocol satisfied by all provider adapters."""

    provider_name: ProviderName
    model_name: str

    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> ProviderResponse:
        """Generates a raw completion response."""
        ...


GEMINI_MODEL_ALIASES: dict[str, str] = {
    "gemini-2.5-flash": "gemini-3.8-flash",
    "gemini-2.5-flash-lite": "gemini-3.5-flash-lite",
    "gemini-2.0-flash": "gemini-3.8-flash",
}


class GeminiProvider:
    """Official Google GenAI SDK adapter (google-genai)."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        api_key: str | None = None,
        sdk_client: Any | None = None,
    ) -> None:
        self.provider_name: ProviderName = "gemini"
        self.model_name = model_name

        if sdk_client is not None:
            self.client = sdk_client
        elif api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            raise ProviderError(
                code="MISSING_KEY",
                provider=self.provider_name,
                retryable=False,
                message="GEMINI_API_KEY is required for GeminiProvider",
            )

    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> ProviderResponse:
        # Convert messages to Gemini Content objects
        contents: list[Any] = []
        for m in messages:
            role = "user" if m.get("role") == "user" else "model"
            text = m.get("content", "")
            contents.append(
                genai_types.Content(
                    role=role,
                    parts=[genai_types.Part.from_text(text=text)],
                )
            )

        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=1024,
        )

        resolved_model = GEMINI_MODEL_ALIASES.get(self.model_name, self.model_name)
        try:
            response = self.client.models.generate_content(
                model=resolved_model,
                contents=contents,
                config=config,
            )
            raw_text = getattr(response, "text", "") or ""
            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or 0

            return ProviderResponse(
                raw_text=raw_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_name=self.model_name,
            )
        except genai_errors.APIError as exc:
            code = "UNKNOWN_ERROR"
            retryable = False
            status_code = getattr(exc, "code", None)

            if status_code == 429:
                code = "RATE_LIMITED"
                retryable = True
            elif status_code in (500, 502, 503, 504):
                code = "SERVER_ERROR"
                retryable = True
            elif status_code in (401, 403):
                code = "AUTH_ERROR"
                retryable = False
            elif status_code == 400:
                code = "INVALID_REQUEST"
                retryable = False
            else:
                code = f"API_ERROR_{status_code}"

            raise ProviderError(
                code=code,
                provider=self.provider_name,
                retryable=retryable,
                message=str(exc),
                original_exception=exc,
            ) from exc
        except TimeoutError as exc:
            raise ProviderError(
                code="TIMEOUT",
                provider=self.provider_name,
                retryable=True,
                message="Gemini request timed out",
                original_exception=exc,
            ) from exc
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(
                code="UNEXPECTED_ERROR",
                provider=self.provider_name,
                retryable=False,
                message=str(exc),
                original_exception=exc,
            ) from exc


class AnthropicProvider:
    """Official Anthropic SDK adapter (anthropic)."""

    def __init__(
        self,
        model_name: str = "claude-3-5-haiku-latest",
        api_key: str | None = None,
        sdk_client: Any | None = None,
    ) -> None:
        self.provider_name: ProviderName = "anthropic"
        self.model_name = model_name

        if sdk_client is not None:
            self.client = sdk_client
        elif api_key:
            self.client = anthropic.Anthropic(api_key=api_key)
        else:
            raise ProviderError(
                code="MISSING_KEY",
                provider=self.provider_name,
                retryable=False,
                message="ANTHROPIC_API_KEY is required for AnthropicProvider",
            )

    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> ProviderResponse:
        formatted_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m.get("role") in ("user", "assistant")
        ]

        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=1024,
                system=system_prompt,
                messages=formatted_messages,
            )
            raw_text = response.content[0].text if response.content else ""
            input_tokens = getattr(response.usage, "input_tokens", 0) or 0
            output_tokens = getattr(response.usage, "output_tokens", 0) or 0

            return ProviderResponse(
                raw_text=raw_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_name=self.model_name,
            )
        except anthropic.RateLimitError as exc:
            raise ProviderError(
                code="RATE_LIMITED",
                provider=self.provider_name,
                retryable=True,
                message=str(exc),
                original_exception=exc,
            ) from exc
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise ProviderError(
                code="AUTH_ERROR",
                provider=self.provider_name,
                retryable=False,
                message=str(exc),
                original_exception=exc,
            ) from exc
        except anthropic.BadRequestError as exc:
            raise ProviderError(
                code="INVALID_REQUEST",
                provider=self.provider_name,
                retryable=False,
                message=str(exc),
                original_exception=exc,
            ) from exc
        except (anthropic.InternalServerError, anthropic.APITimeoutError) as exc:
            code = "TIMEOUT" if isinstance(exc, anthropic.APITimeoutError) else "SERVER_ERROR"
            raise ProviderError(
                code=code,
                provider=self.provider_name,
                retryable=True,
                message=str(exc),
                original_exception=exc,
            ) from exc
        except anthropic.APIStatusError as exc:
            retryable = exc.status_code in (429, 500, 502, 503, 504)
            code = (
                "RATE_LIMITED"
                if exc.status_code == 429
                else ("SERVER_ERROR" if retryable else f"API_ERROR_{exc.status_code}")
            )
            raise ProviderError(
                code=code,
                provider=self.provider_name,
                retryable=retryable,
                message=str(exc),
                original_exception=exc,
            ) from exc
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(
                code="UNEXPECTED_ERROR",
                provider=self.provider_name,
                retryable=False,
                message=str(exc),
                original_exception=exc,
            ) from exc


class OpenAIProvider:
    """Official OpenAI SDK adapter (openai)."""

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        api_key: str | None = None,
        sdk_client: Any | None = None,
    ) -> None:
        self.provider_name: ProviderName = "openai"
        self.model_name = model_name

        if sdk_client is not None:
            self.client = sdk_client
        elif api_key:
            self.client = openai.OpenAI(api_key=api_key)
        else:
            raise ProviderError(
                code="MISSING_KEY",
                provider=self.provider_name,
                retryable=False,
                message="OPENAI_API_KEY is required for OpenAIProvider",
            )

    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> ProviderResponse:
        all_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for m in messages:
            all_messages.append({"role": m["role"], "content": m["content"]})

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                response_format={"type": "json_object"},
                messages=all_messages,
            )
            raw_text = response.choices[0].message.content or "{}"
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage, "completion_tokens", 0) or 0

            return ProviderResponse(
                raw_text=raw_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_name=self.model_name,
            )
        except openai.RateLimitError as exc:
            raise ProviderError(
                code="RATE_LIMITED",
                provider=self.provider_name,
                retryable=True,
                message=str(exc),
                original_exception=exc,
            ) from exc
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise ProviderError(
                code="AUTH_ERROR",
                provider=self.provider_name,
                retryable=False,
                message=str(exc),
                original_exception=exc,
            ) from exc
        except openai.BadRequestError as exc:
            raise ProviderError(
                code="INVALID_REQUEST",
                provider=self.provider_name,
                retryable=False,
                message=str(exc),
                original_exception=exc,
            ) from exc
        except (openai.InternalServerError, openai.APITimeoutError) as exc:
            code = "TIMEOUT" if isinstance(exc, openai.APITimeoutError) else "SERVER_ERROR"
            raise ProviderError(
                code=code,
                provider=self.provider_name,
                retryable=True,
                message=str(exc),
                original_exception=exc,
            ) from exc
        except openai.APIStatusError as exc:
            retryable = exc.status_code in (429, 500, 502, 503, 504)
            code = (
                "RATE_LIMITED"
                if exc.status_code == 429
                else ("SERVER_ERROR" if retryable else f"API_ERROR_{exc.status_code}")
            )
            raise ProviderError(
                code=code,
                provider=self.provider_name,
                retryable=retryable,
                message=str(exc),
                original_exception=exc,
            ) from exc
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(
                code="UNEXPECTED_ERROR",
                provider=self.provider_name,
                retryable=False,
                message=str(exc),
                original_exception=exc,
            ) from exc


class ScriptedProvider:
    """Deterministic offline demo provider requiring zero API keys."""

    def __init__(
        self,
        model_name: str = "scripted-demo",
        force_error: ProviderError | None = None,
    ) -> None:
        self.provider_name: ProviderName = "scripted"
        self.model_name = model_name
        self.force_error = force_error
        self.call_count: int = 0

    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> ProviderResponse:
        self.call_count += 1
        if self.force_error is not None:
            raise self.force_error

        # Extract last user message
        last_user_content = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_content = m.get("content", "")
                break

        lower_query = last_user_content.lower()

        if "rate limit" in lower_query or "429" in lower_query:
            answer = (
                "HTTP 429 indicates rate limiting. Clients should implement exponential "
                "backoff with jitter to reduce contention and retry transient errors."
            )
            category = "technical"
            key_points = [
                "429 means too many requests sent within time window",
                "Exponential backoff doubles delay between consecutive retries",
                "Jitter desynchronizes concurrent retrying clients",
            ]
            questions = [
                "Would you like an example of backoff implementation in Python?",
                "Are you configuring retry policies for Gemini or Anthropic?",
            ]
        elif "iceberg" in lower_query or "lake" in lower_query or "delta" in lower_query:
            answer = (
                "Apache Iceberg is an open table format for huge analytic datasets. "
                "It enables ACID transactions, time travel queries, and schema evolution."
            )
            category = "technical"
            key_points = [
                "ACID guarantees via atomic metadata commits",
                "Hidden partitioning eliminates partition specification in queries",
                "Full schema evolution without rewriting data files",
            ]
            questions = [
                "Do you want to compare Apache Iceberg with Delta Lake?",
                "Would you like to see how Apache Spark writes to Iceberg tables?",
            ]
        else:
            answer = (
                f"Thank you for your question: '{last_user_content[:60]}...'. "
                "I am running in offline scripted demo mode with zero external dependencies."
            )
            category = "general"
            key_points = [
                "Zero-key offline demo provider active",
                "Deterministic JSON output complying with schema",
                "Telemetry and costs tracked identically to live providers",
            ]
            questions = [
                "Would you like to test a multi-provider fallback scenario?",
                "Can I demonstrate token tracking or JSON auto-repair?",
            ]

        reply = StructuredReply(
            answer=answer,
            category=category,  # type: ignore[arg-type]
            key_points=key_points,
            follow_up_questions=questions,
            confidence=0.95,
        )

        return ProviderResponse(
            raw_text=reply.model_dump_json(),
            input_tokens=120,
            output_tokens=85,
            model_name=self.model_name,
        )
