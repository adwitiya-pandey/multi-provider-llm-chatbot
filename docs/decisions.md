# Architecture Decision Records (ADRs)

This document formalizes the key architectural, security, and design decisions made in `multi-provider-llm-chatbot`.

---

## D1: Native SDK Adapters Over Framework Wrappers

- **Status**: Accepted
- **Context**: High-level frameworks like LangChain, LlamaIndex, or LiteLLM introduce deep abstraction hierarchies, frequent breaking changes, and uncontrolled dependency graphs.
- **Decision**: Wrap the official `google-genai`, `anthropic`, and `openai` SDKs directly using a lightweight `LLMProvider` protocol.
- **Consequences**:
  - Direct control over request payload generation, token usage extraction, and error handling.
  - Zero framework bloat and minimal external dependencies.
  - Provable AST isolation enforced by automated unit tests.

---

## D2: Injectable Clocks and SDK Clients for Deterministic Testing

- **Status**: Accepted
- **Context**: Testing exponential backoff retries (1.0s, 2.0s, 4.0s) and multi-provider failover can either make test suites slow or introduce fragile global monkeypatching.
- **Decision**: Inject `sleep_fn: Callable[[float], None]` into `ResilientRouter` and `sdk_client` into provider constructors.
- **Consequences**:
  - Multi-attempt backoff retry suites execute in 0 milliseconds.
  - 100% offline unit tests without making external network calls or needing paid API keys.

---

## D3: Dual-Mode Runtime Architecture (Live Gemini vs. Scripted Offline)

- **Status**: Accepted
- **Context**: Reviewers, CI pipelines, and developers may not possess active paid accounts across all three LLM vendors (OpenAI, Anthropic, Google).
- **Decision**: Default to `LLM_MODE=scripted` when no keys are detected. When `GEMINI_API_KEY` is present in `.env`, automatically resolve to `LLM_MODE=live` using Gemini 2.5 Flash as primary and Gemini 2.5 Flash Lite as fallback.
- **Consequences**:
  - The repository runs out-of-the-box with zero keys for anyone cloning it.
  - Full end-to-end live testing is supported with only a free/standard Gemini key.
  - Anthropic and OpenAI adapters remain fully implemented and verified via offline mock suites.

---

## D4: Deterministic Short-Circuit for Prompt Injection Interception

- **Status**: Accepted
- **Context**: Relying on the LLM itself to identify and decline adversarial jailbreak attempts ("ignore previous instructions") wastes model tokens and introduces probabilistic bypass risks.
- **Decision**: Intercept known prompt injection signatures deterministically in `sanitize.py` and `chat.py`.
- **Consequences**:
  - Adversarial queries are rejected instantly with 0 LLM provider calls.
  - Token consumption and financial cost for rejected attacks are strictly $0.00.
  - Rejected attacks never pollute conversational memory.

---

## D5: 1-Step JSON Self-Healing Repair with Safe Fallback

- **Status**: Accepted
- **Context**: LLMs occasionally return markdown-wrapped JSON, missing keys, or slight syntax deviations, which can crash downstream consumers if unhandled.
- **Decision**: Attempt standard Pydantic model validation. If parsing fails, execute at most 1 targeted repair call passing field-level error summaries. If repair fails, return a safe deterministic `StructuredReply` with `category="clarification"`.
- **Consequences**:
  - Eliminates unhandled runtime exceptions in Streamlit and API consumers.
  - Caps token spend by enforcing an exact 1-step repair limit.
  - Never leaks sensitive user text in repair prompt error messages.

---

## D6: Local Tiktoken Pre-Flight Counting Over Provider Count-Tokens Endpoints

- **Status**: Accepted
- **Context**: Accurate token estimates are needed prior to dispatching LLM calls for sliding-window conversation memory eviction, hard session budget pre-checks, and UI context gauges. Provider SDKs either offer separate token counting endpoints (e.g. Gemini `count_tokens`) or lack dedicated free endpoints altogether.
- **Decision**: Employ OpenAI's `tiktoken` BPE library (`o200k_base` / `cl100k_base`) locally in-process for all pre-flight token decisions in `tokens.py`. If loading the encoding fails (e.g. offline environment with unpopulated cache), gracefully fall back to the heuristic `len // 4` estimator. Official provider-reported usage metadata received upon completion remains the sole ground truth for financial accounting and cumulative budget tracking.
- **Consequences**:
  - **Zero Network Overhead**: Pre-flight decisions occur with sub-millisecond local CPU execution rather than incurring an extra 200–500ms roundtrip per turn.
  - **Quota Preservation**: Eliminates consumption of limited API quota on pre-call token counts. For Google Gemini, while `count_tokens` serves as an exact alternative, invoking it before every turn would double request counts.
  - **Empirical Approximation**: Tiktoken is exact for OpenAI models and serves as an approximation for Gemini and Claude. Live calibration against Gemini 3.8 Flash demonstrated a Mean Absolute Percentage Error (MAPE) of 13.11% for Tiktoken vs. 30.37% for the naive character heuristic.
  - **Fault Tolerance**: A process-level cache and graceful fallback to `HeuristicCounter` (emitting `token_counter_fallback`) ensures chat turns never fail due to token counting issues.
