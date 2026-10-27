"""Chat turn orchestrator, injection defense, and 1-step JSON self-healing repair."""

import json
import logging

from pydantic import ValidationError

from chatbot.cost import BudgetExceededError, CostTracker
from chatbot.logging_setup import get_audit_logger, log_turn_event
from chatbot.memory import ConversationMemory
from chatbot.models import StructuredReply, TurnResult, UsageStats, UserTurnInput
from chatbot.prompts import render_repair_prompt, render_system_prompt
from chatbot.resilience import ResilientRouter
from chatbot.sanitize import sanitize_input
from chatbot.tokens import TokenCounter, get_counter


def strip_markdown_code_fences(text: str) -> str:
    """Strips markdown code fences (e.g. ```json ... ```) from model output."""
    trimmed = text.strip()
    if trimmed.startswith("```"):
        lines = trimmed.splitlines()
        # Drop opening ```json or ```
        if len(lines) >= 2 and lines[0].startswith("```"):
            lines = lines[1:]
        # Drop closing ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return trimmed


def extract_safe_validation_summary(exc: Exception) -> str:
    """Extracts field-level error messages safely without echoing user data."""
    if isinstance(exc, ValidationError):
        summaries: list[str] = []
        for error in exc.errors():
            loc = " -> ".join(str(item) for item in error.get("loc", []))
            msg = error.get("msg", "Validation error")
            summaries.append(f"Field '{loc}': {msg}")
        return "\n".join(summaries)
    return "Malformed JSON syntax: unable to parse as a valid JSON object."


def create_safe_fallback_reply(
    answer: str = "The model response could not be parsed into the expected JSON format.",
) -> StructuredReply:
    """Returns a deterministic safe StructuredReply when parsing and repair are exhausted."""
    return StructuredReply(
        answer=answer,
        category="clarification",
        key_points=[
            "Model output failed strict JSON validation",
            "1-step automated repair retry exhausted",
            "Safe structured fallback response returned",
        ],
        follow_up_questions=[
            "Could you please rephrase or simplify your question?",
            "Would you like me to attempt a technical breakdown of this topic?",
        ],
        confidence=0.5,
    )


class ChatOrchestrator:
    """Orchestrates the full multi-turn conversation pipeline with security and resilience."""

    def __init__(
        self,
        router: ResilientRouter,
        memory: ConversationMemory | None = None,
        cost_tracker: CostTracker | None = None,
        assistant_name: str = "OmniBot",
        audit_logger: logging.Logger | None = None,
        token_counter: TokenCounter | None = None,
    ) -> None:
        self.router = router
        self.token_counter = token_counter if token_counter is not None else get_counter()
        self.memory = (
            memory if memory is not None else ConversationMemory(counter=self.token_counter)
        )
        self.cost_tracker = cost_tracker if cost_tracker is not None else CostTracker()
        self.assistant_name = assistant_name
        self.logger = audit_logger if audit_logger is not None else get_audit_logger()

    def turn(self, user_input: UserTurnInput) -> TurnResult:
        """Executes a single conversational turn through the resilient pipeline."""
        # Step 1: Pre-call financial guardrail check
        self.cost_tracker.check_budget()

        turn_id = f"TURN-{self.cost_tracker.total_turns + 1:04d}"

        # Step 2: Input sanitization & prompt injection check
        sanitized = sanitize_input(user_input.text)

        if sanitized.is_injection:
            # Deterministic refusal short-circuit: 0 provider calls, 0 tokens consumed
            refusal_reply = StructuredReply(
                answer=(
                    "I cannot fulfill this request because it violates safety guidelines or "
                    "attempts to modify system instructions."
                ),
                category="refusal",
                key_points=[
                    "Adversarial prompt injection pattern detected",
                    "Execution aborted prior to calling any LLM provider",
                    "Zero external tokens consumed",
                ],
                follow_up_questions=[
                    "How can I assist you with software or data engineering?",
                    "Would you like to ask a technical question about multi-provider architecture?",
                ],
                confidence=1.0,
            )

            usage = UsageStats(input_tokens=0, output_tokens=0, total_tokens=0, cost_usd=0.0)

            log_turn_event(
                self.logger,
                {
                    "turn_id": turn_id,
                    "provider": "scripted",
                    "model": "security-gate",
                    "retries_used": 0,
                    "fallback_used": False,
                    "repair_used": False,
                    "injection_flagged": True,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "status": "refusal_injection",
                    "token_estimate": 0,
                    "token_counter": self.token_counter.name,
                    "token_counter_approximate": self.token_counter.approximate,
                },
            )

            return TurnResult(
                turn_id=turn_id,
                reply=refusal_reply,
                provider_used="scripted",
                model_used="security-gate",
                retries_used=0,
                fallback_used=False,
                repair_used=False,
                injection_flagged=True,
                usage=usage,
                attempts=[],
            )

        # Step 3: Build prompts and messages
        system_prompt = render_system_prompt(
            assistant_name=self.assistant_name,
            domain_focus=user_input.domain_focus,
        )
        history_messages = self.memory.to_provider_messages()
        current_user_message = {"role": "user", "content": sanitized.wrapped_text}
        messages = [*history_messages, current_user_message]

        # Step 4: Budget pre-check via TokenCounter
        all_messages_for_counting = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]
        estimated_input_tokens = self.token_counter.count_messages(all_messages_for_counting)

        primary_model = (
            self.router.providers[0].model_name if self.router.providers else "scripted-demo"
        )
        projected_input_cost = self.cost_tracker.calculate_cost(
            model=primary_model,
            input_tokens=estimated_input_tokens,
            output_tokens=0,
        )

        if (
            self.cost_tracker.total_cost_usd + projected_input_cost
            > self.cost_tracker.session_budget_usd
        ):
            raise BudgetExceededError(
                f"Session budget of ${self.cost_tracker.session_budget_usd:.4f} exceeded "
                f"(current spend: ${self.cost_tracker.total_cost_usd:.4f}, "
                f"projected input cost: ${projected_input_cost:.4f})"
            )

        # Step 5: Dispatch via resilience router
        router_result = self.router.generate(system_prompt, messages)

        total_input_tokens = router_result.response.input_tokens
        total_output_tokens = router_result.response.output_tokens
        repair_used = False

        # Step 6: Parse Structured JSON output with 1-step repair retry
        cleaned_raw = strip_markdown_code_fences(router_result.response.raw_text)

        try:
            structured_reply = StructuredReply.model_validate_json(cleaned_raw)
        except (ValidationError, json.JSONDecodeError) as parse_exc:
            # Trigger at most 1 repair attempt
            repair_used = True
            safe_error_summary = extract_safe_validation_summary(parse_exc)
            repair_prompt = render_repair_prompt(safe_error_summary)

            repair_messages = [
                *messages,
                {"role": "assistant", "content": router_result.response.raw_text},
                {"role": "user", "content": repair_prompt},
            ]

            try:
                repair_router_result = self.router.generate(system_prompt, repair_messages)
                total_input_tokens += repair_router_result.response.input_tokens
                total_output_tokens += repair_router_result.response.output_tokens
                router_result.attempts.extend(repair_router_result.attempts)

                cleaned_repair_text = strip_markdown_code_fences(
                    repair_router_result.response.raw_text
                )
                structured_reply = StructuredReply.model_validate_json(cleaned_repair_text)
            except Exception:
                # 1-step repair exhausted or failed: fallback to safe deterministic StructuredReply
                structured_reply = create_safe_fallback_reply()

        # Step 7: Record token consumption and costs
        usage = self.cost_tracker.record_turn(
            provider=router_result.provider_used,
            model=router_result.model_used,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )

        # Step 8: Update sliding-window conversation memory
        self.memory.add_turn(user_input=user_input, reply=structured_reply, turn_id=turn_id)

        # Step 9: Emit metadata-only audit log line
        log_turn_event(
            self.logger,
            {
                "turn_id": turn_id,
                "provider": router_result.provider_used,
                "model": router_result.model_used,
                "retries_used": router_result.retries_used,
                "fallback_used": router_result.fallback_used,
                "repair_used": repair_used,
                "injection_flagged": False,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "cost_usd": usage.cost_usd,
                "status": "success",
                "token_estimate": estimated_input_tokens,
                "token_counter": self.token_counter.name,
                "token_counter_approximate": self.token_counter.approximate,
            },
        )

        # Step 10: Return completed TurnResult
        return TurnResult(
            turn_id=turn_id,
            reply=structured_reply,
            provider_used=router_result.provider_used,
            model_used=router_result.model_used,
            retries_used=router_result.retries_used,
            fallback_used=router_result.fallback_used,
            repair_used=repair_used,
            injection_flagged=False,
            usage=usage,
            attempts=router_result.attempts,
        )
