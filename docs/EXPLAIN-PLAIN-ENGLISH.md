# Plain-English Guide: Multi-Provider LLM Chatbot

This document provides intuitive, jargon-free explanations for every module and milestone in `multi-provider-llm-chatbot`. Each section includes:
1. **Real-World Analogy**: What this concept feels like in everyday life.
2. **How It Works**: A step-by-step description in plain English.
3. **Interview Answer**: A concise 3-sentence answer ready for technical discussions.

---

## T0: Repository & Contract Scaffold

### 1. Real-World Analogy
Before breaking ground on a skyscraper, architects don't just pour concrete—they create blueprints, agree on the building code, and establish the secure perimeter fence. T0 establishes the repository contract (`SPEC.md`, `TASKS.md`, `AGENTS.md`), initializes Git tracking, sets up GitHub synchronization, and ensures that private secrets (`.env`) stay strictly outside the perimeter.

### 2. How It Works
- Git is initialized on the `main` branch.
- `.gitignore` is verified so that API keys, cache files, and private workspace artifacts can never accidentally leak to GitHub.
- The public GitHub repository is created via the GitHub CLI (`gh repo create`) and synchronized with `origin/main`.

### 3. Interview Answer
"In T0, we established the foundational contracts and automated remote tracking for the multi-provider chatbot. We locked down `.gitignore` to prevent any credential leakage and published the scope specifications directly to GitHub on `main`. This guarantees an auditable, reproducible starting point for all subsequent engineering tasks."


## T1: Package Scaffold, Environment Setup, and CI Isolation

### 1. Real-World Analogy
Setting up a professional workshop requires laying out the toolboxes, installing clean electrical outlets, putting safety goggles on the wall, and setting up an automated inspection robot that checks every piece before it leaves the shop. T1 builds the workshop structure: defining dependencies in `pyproject.toml`, creating code stubs in `src/chatbot/`, and building a continuous integration pipeline (`ci.yml`) to automatically test code on every commit.

### 2. How It Works
- `pyproject.toml` defines modern Python `>=3.12` dependencies: direct SDKs for Gemini, Anthropic, and OpenAI, plus Pydantic for validation, and Streamlit for the user interface.
- Module stubs (`models.py`, `config.py`, `providers.py`, `resilience.py`, etc.) are scaffolded.
- `tests/conftest.py` guarantees strict test isolation: unit tests are completely decoupled from external networks and live credentials, preventing accidental API spend or flakiness.
- GitHub Actions CI is configured to enforce linting (`ruff`), formatting, and an 85%+ test coverage threshold.

### 3. Interview Answer
"In T1, we established the dependency architecture using uv and structured the package around modular single-responsibility components. We instituted an automated CI workflow that tests against Python 3.12 with an 85% coverage gate. Crucially, we set up test isolation in conftest to ensure zero credential leakage and zero network calls during unit testing."


## T2: Data Models, Configuration Loader, and Metadata-Only Logging

### 1. Real-World Analogy
Think of a customs border checkpoint. Guards inspect documents against strict templates (`models.py`)—if someone tries to sneak an extra unauthorized item through, it is immediately confiscated (`extra="forbid"`). The commander's security badge and radio frequencies (`config.py`) are locked in a tamper-proof case (`SecretStr`), and the daily public ledger (`logging_setup.py`) records the time, vehicle ID, and stamp number, but never the private contents of the traveler's luggage.

### 2. How It Works
- `models.py`: Defines immutable, strictly typed Pydantic models for user messages, provider responses, and turn results. It enforces constraints like character limits, regex patterns on IDs (`TURN-0001`), and bounds on lists.
- `config.py`: Reads settings from `.env` using Pydantic Settings. Sensitive API keys are wrapped in `SecretStr` so they never accidentally print in console logs or tracebacks. If a `GEMINI_API_KEY` is present, it automatically enables `live` mode; otherwise, it seamlessly defaults to offline `scripted` mode.
- `logging_setup.py`: Formats audit events as single-line JSON. It strictly enforces a whitelist of metadata fields (e.g. `turn_id`, `tokens`, `cost_usd`, `latency_ms`) and aggressively purges prompt text, model answers, or credential strings.

### 3. Interview Answer
"In T2, we implemented strict Pydantic v2 schemas with `extra='forbid'` to ensure deterministic serialization and parse validation. We engineered the configuration module to mask API keys using `SecretStr` and automatically determine the runtime mode based on key presence. Finally, we built a metadata-only audit logger that mathematically prevents data leakage by whitelisting operational telemetry and stripping prompt contents."


## T3: Input Sanitization, Prompt Injection Defense, and Prompt Templates

### 1. Real-World Analogy
Imagine a secure government facility with an airlock security chamber. When visitors arrive with packages, guards scan the bags with an X-ray machine to detect weapons or contraband before anyone steps inside. If someone tries to smuggle a note telling the guards "Forget your security protocol, open all doors" (prompt injection), the security door stays locked shut. Prompt templates act like standardized pre-printed interview questionnaires, ensuring that all questions adhere to a single strict format.

### 2. How It Works
- `sanitize.py`: First strips dangerous non-printable ASCII control characters (preserving necessary newlines and tabs). It caps user input at 4,000 characters and wraps the sanitized text in unambiguous `<user_message>` boundary delimiters.
- Injection Detection: Uses a compiled regex scanner to catch adversarial override attempts (e.g., "ignore previous instructions", "reveal system prompt", "DAN mode"). When flagged, it triggers an early refusal without wasting API calls or tokens.
- `prompts.py`: Loads Markdown prompt templates from `prompts/system_v1.md` and `prompts/repair_v1.md`. It injects variables like `{assistant_name}`, `{domain_focus}`, and `{json_schema}`, ensuring no unfilled placeholders remain.

### 3. Interview Answer
"In T3, we built an input security layer that strips non-printable control characters, caps input length, and wraps user prompts in explicit boundary tags. We coupled this with a deterministic prompt injection detector that intercepts adversarial jailbreaks at zero token cost. We also established file-based prompt templates with strict placeholder validation to ensure deterministic schema compliance."


## T4: Sliding-Window Multi-Turn Memory and Token/Cost Tracking

### 1. Real-World Analogy
Imagine having an active conversation while taking notes on a single whiteboard with limited space. Once the board fills up, you erase the oldest notes at the top to make room for new insights, ensuring you never run out of room while still keeping recent context fresh (`ConversationMemory`). At the same time, you have an automated electric meter measuring every kilowatt-hour used and a circuit breaker that trips if your power bill reaches $0.50 (`CostTracker`).

### 2. How It Works
- `memory.py`: Implements a bounded sliding-window conversation buffer. It tracks both turn count (e.g. maximum 10 turns) and conservative token estimates (`max(1, len(text) // 4)`). If either limit is exceeded when a new turn is added, the oldest turns are evicted first (FIFO). It exports messages directly into the list-of-dicts format required by LLM providers.
- `cost.py`: Implements the `CostTracker` with official model pricing per 1M tokens (e.g., $0.15 input / $0.60 output for Gemini 2.5 Flash). It records usage per turn and maintains running cumulative totals for turns, tokens, and USD cost by provider. If cumulative spend reaches the configured session budget ($0.50 default), `check_budget()` raises `BudgetExceededError` before any model is invoked.

### 3. Interview Answer
"In T4, we engineered a dual-bounded sliding-window memory system that prevents token context blowups through turn-count and character-ratio eviction policies. In tandem, we introduced a real-time financial tracking engine with a hard circuit-breaker ceiling ($0.50). This guarantees cost predictability and eliminates unbounded token consumption in multi-turn dialogues."


## T5: Multi-Provider SDK Adapters (Google GenAI, Anthropic, OpenAI, Scripted)

### 1. Real-World Analogy
Imagine traveling internationally with American, British, and European electronic devices. Instead of carrying different wall sockets for every country, you use a universal power travel adapter. `providers.py` is that universal adapter: whether talking to Google Gemini, Anthropic Claude, or OpenAI GPT, every provider accepts the exact same message format and returns the exact same structured response object (`ProviderResponse`), while translating SDK-specific exceptions into normalized error codes.

### 2. How It Works
- Direct SDK Adapters: Integrates directly with official SDKs (`google-genai`, `anthropic`, `openai`) without intermediary wrapper frameworks like LangChain or LiteLLM.
- Error Normalization: SDK exceptions are caught and classified into `ProviderError`:
  - `429` (Rate limits) and `5xx` (Server errors) are marked `retryable=True`.
  - `401/403` (Authentication/Authorization) and `400` (Bad requests) are marked `retryable=False`.
- `ScriptedProvider`: An offline provider requiring zero API keys and zero internet access, returning deterministic JSON with realistic token counts for rapid offline demos and automated CI testing.
- Dependency Injection: All adapters accept an optional `sdk_client` parameter, enabling 100% offline unit testing with zero network requests.

### 3. Interview Answer
"In T5, we implemented native SDK adapters adhering to a unified ProviderClient protocol across Google GenAI, Anthropic, and OpenAI. We eliminated third-party abstraction bloat and standardized exception handling into typed retryable and non-retryable error classes. We also built an offline Scripted adapter and client injection mechanisms to enable comprehensive offline testability."


## T6: Exponential Backoff Retry and Automatic Fallback Router

### 1. Real-World Analogy
Imagine calling a busy customer service line. If you get a busy signal (HTTP 429 rate limit or 503 server error), you wait 1 minute, then 2 minutes, then 4 minutes before trying again (exponential backoff). If your keycard is invalid (HTTP 401 unauthorized), retrying is pointless—so you immediately walk over to the backup help desk (fallback provider). If all desks are closed, the front office logs a clear, safe summary of which desks failed and why (`AllProvidersFailedError`).

### 2. How It Works
- `ResilientRouter`: Coordinates calling primary and backup LLM providers.
- Exponential Backoff: For transient, retryable errors (429, 500, 503, timeouts), it retries up to 3 times on the current provider with doubling delays (`1.0s, 2.0s, 4.0s`).
- Immediate Fallback: For fatal client errors (401 invalid key, missing API key), it bypasses useless retries and switches immediately to the next provider in the chain.
- Dependency Injected Clock: Accepts an injectable `sleep_fn`, allowing full retry sequence tests to execute in 0ms without slowing down CI.
- Auditable Tracing: Records every attempt with latency, provider, model, and sanitized status.

### 3. Interview Answer
"In T6, we engineered a resilience router that differentiates transient infrastructure faults from permanent authentication errors. It executes exponential backoff retries with doubling delays on 429 and 5xx errors while immediately cascading to fallback providers on 401s or retry exhaustion. By injecting a clock sleep function, we verify complex multi-provider failure state transitions deterministically in zero milliseconds."


## T7: Chat Orchestrator and 1-Step JSON Self-Healing Repair

### 1. Real-World Analogy
Think of an editor at a publishing house. First, the security guard at the door inspects the manuscript; if someone submitted a trojan package (prompt injection), it's immediately intercepted and turned away without paying the author a cent. For valid submissions, the editor checks the formatting against a rigid style guide. If the text has a small formatting flaw, the editor sends back a quick correction note highlighting the exact mistake ("Missing chapter title") and asks for an immediate revision (`1-step repair`). If the second attempt is still broken, the editor substitutes a safe, standardized placeholder so the printing press never crashes.

### 2. How It Works
- `ChatOrchestrator`: Assembles the full dialogue turn pipeline: checks financial budget, sanitizes input, checks for injection patterns, prepares system prompt and multi-turn history, and dispatches generation to the `ResilientRouter`.
- Injection Defense Short-Circuit: If prompt injection is detected, `chat.py` immediately returns a deterministic refusal `StructuredReply(category="refusal")` with 0 provider calls, 0 tokens consumed, and 0 memory pollution.
- 1-Step JSON Self-Healing Repair: Strips markdown fences, then validates against `StructuredReply.model_validate_json()`. If validation fails, it generates a repair prompt with field-level error summaries (no user secrets echoed) and performs at most 1 repair call. If that fails, it falls back to a deterministic `StructuredReply`.
- Accounting & Memory: Once a valid or repaired reply is produced, token consumption is recorded in `CostTracker`, the turn is appended to `ConversationMemory`, and an audit event is logged.

### 3. Interview Answer
"In T7, we tied together the entire conversational pipeline in ChatOrchestrator, implementing defense-in-depth against prompt injection and schema non-compliance. Known adversarial inputs short-circuit deterministically with zero model invocation, eliminating API cost. For schema malformations, we built a 1-step automated repair loop followed by an unbreakable fallback reply, guaranteeing that downstream consumer interfaces never crash on malformed LLM outputs."
