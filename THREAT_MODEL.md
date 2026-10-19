# Threat Model: Multi-Provider LLM Chatbot

This document evaluates the security architecture of `multi-provider-llm-chatbot` using the **STRIDE** methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) mapped to security requirements `S1` through `S8`.

---

## 1. STRIDE Threat Analysis Matrix

| Threat Category | Potential Attack Vector | Impact | Mitigation Mechanism | Requirement | Verification Test |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Spoofing** | Attacker injects forged API credentials or fake environment configurations | Unauthorized model usage or key theft | Keys loaded as `SecretStr` via `pydantic-settings`; test suites run with ambient keys strictly isolated | **S1, S8** | `tests/test_security.py`, `tests/conftest.py` |
| **Tampering** | Prompt injection attacks attempt to override system rules via `<user_message>` breakouts | Hijacked model behavior, policy bypass | Regex scanning for 14+ injection patterns; explicit `<user_message>` tagging; strict Pydantic output validation | **S3, S4, S6** | `tests/test_sanitize.py`, `tests/test_chat.py`, `tests/test_models.py` |
| **Repudiation** | User or caller disputes interaction history or token expenditure | Inability to audit spend or operational failures | Metadata-only structured JSON audit logging recording `turn_id`, tokens, cost, latency, and status | **S5** | `tests/test_logging.py` |
| **Information Disclosure** | Leakage of private API keys, system instructions, or sensitive user queries in logs/UI | Credential exposure, privacy violation | Audit logger enforces strict metadata whitelist; `extra="forbid"` on schemas; `.env` excluded in `.gitignore` | **S1, S5** | `tests/test_logging.py`, `tests/test_security.py` |
| **Denial of Service** | Unbounded input length, infinite retry loops, or wallet-draining query floods | Service unavailability, financial exhaustion | 4,000-character input cap; 3-retry maximum with exponential backoff; hard `$0.50` session budget ceiling | **S3, S7** | `tests/test_sanitize.py`, `tests/test_resilience.py`, `tests/test_cost.py` |
| **Elevation of Privilege** | Supply-chain attacks via vulnerable wrapper packages | Arbitrary code execution or hijacked SDK logic | Zero third-party LLM frameworks (LangChain/LiteLLM banned); direct official SDKs isolated strictly to `providers.py` | **S2** | `tests/test_boundaries.py` |

---

## 2. Security Requirements (S1–S8) Deep Dive

### S1: Credential Protection and Environment Safety
- **Threat**: Accidental commitment of `.env` files or exposure of raw API keys in stack traces and console outputs.
- **Controls**:
  - `.env` and `.env.*` are explicitly listed in `.gitignore`.
  - `.env.example` contains only descriptive non-secret placeholders (`your-gemini-key-here`).
  - All secret keys in `config.py` are typed as `pydantic.SecretStr`, ensuring `str()` and `repr()` mask the secret value as `**********`.

### S2: Architectural AST Boundary Isolation
- **Threat**: Contamination of business logic by bloated or vulnerable third-party LLM orchestration libraries.
- **Controls**:
  - `google.genai`, `anthropic`, and `openai` may ONLY be imported within `src/chatbot/providers.py`.
  - Static AST analysis parses all `.py` files to guarantee that `langchain`, `llama_index`, and `litellm` are strictly banned from the repository.

### S3: Input Hardening and Sanitization
- **Threat**: Buffer overflow attempts, invisible Unicode control characters, and delimiter breakout injection attacks.
- **Controls**:
  - Strips non-printable ASCII control characters while preserving legitimate formatting whitespace (`\n`, `\t`, `\r`).
  - Strict input length cap at 4,000 characters.
  - User text is wrapped in explicit `<user_message>` boundary tags.

### S4: Deterministic Prompt Injection Interception
- **Threat**: Attackers attempting to jailbreak the bot into ignoring safety directives or printing secrets.
- **Controls**:
  - Regex pre-filter scans for 14+ adversarial signatures ("ignore previous instructions", "reveal system prompt", "DAN mode").
  - On detection, `ChatOrchestrator` short-circuits instantly, returning a deterministic refusal with 0 external API calls and 0 token cost.

### S5: Zero-Leak Structured Telemetry
- **Threat**: User prompts or proprietary system replies leaking into observability platforms, SIEMs, or log files.
- **Controls**:
  - `logging_setup.py` enforces a strict whitelist of allowed operational metadata fields (`turn_id`, `tokens`, `cost_usd`, `latency_ms`, `status`).
  - Any key containing `text`, `prompt`, `answer`, `key`, or `secret` is purged before serialization.

### S6: Strict Schema Compliance
- **Threat**: Malformed JSON payloads causing unhandled exceptions in consumer applications.
- **Controls**:
  - All data transfer objects enforce `model_config = ConfigDict(extra="forbid", strict=True)`.
  - 1-step automated JSON repair retry heals minor formatting mistakes before safe fallback activation.

### S7: Financial Circuit Breakers
- **Threat**: Runaway retry loops or recursive interactions exhausting API credit quotas.
- **Controls**:
  - `CostTracker` enforces a hard session budget ceiling ($0.50 default).
  - Calling `check_budget()` before provider invocation raises `BudgetExceededError` if the ceiling is reached.

### S8: Deterministic Offline Testing
- **Threat**: Flaky unit tests resulting from network outages or accidental real API spend during development and CI.
- **Controls**:
  - `tests/conftest.py` strips all ambient API keys and forces `LLM_MODE=scripted`.
  - All provider and resilience tests utilize injected fake SDK clients and simulated sleep timers.
