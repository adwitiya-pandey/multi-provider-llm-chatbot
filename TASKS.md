# TASKS: `multi-provider-llm-chatbot`

> **AUTONOMOUS END-TO-END EXECUTION RULE (SINGLE-CHAT WORKFLOW)**:
> Execute **all tasks `T0` through `T12` back-to-back** in a single continuous run without stopping between tasks.
> - Commit each task with Conventional Commits (`Refs: T<N>`), update `PROGRESS.md`, append a plain-English explanation to `docs/EXPLAIN-PLAIN-ENGLISH.md`, and proceed immediately to the next task.
> - Load `GEMINI_API_KEY` from the local gitignored `.env` file (`python-dotenv` / `pydantic-settings`). Never print or commit `.env`.

| Order | Task | Scope |
| :--- | :--- | :--- |
| **T0** | Repository & GitHub creation | `git init`, create public GitHub repo `adwitiya-pandey/multi-provider-llm-chatbot` via `gh repo create` |
| **T1** | Package scaffold & CI | `uv init`, `pyproject.toml`, `.env.example`, `LICENSE`, `.github/workflows/ci.yml`, `docs/sdk_notes.md` verification |
| **T2** | Models, config & logging | `models.py`, `config.py` (`.env` loader), `logging_setup.py` + unit tests |
| **T3** | Input sanitizer & prompt templates | `sanitize.py`, `prompts/system_v1.md`, `prompts/repair_v1.md`, `prompts.py` + unit tests |
| **T4** | Multi-turn memory & cost tracker | `memory.py`, `cost.py` (`CostTracker`, `$0.50` ceiling) + unit tests |
| **T5** | Multi-provider SDK adapters | `providers.py` (`GeminiProvider`, `AnthropicProvider`, `OpenAIProvider`, `ScriptedProvider`) + mocked SDK tests |
| **T6** | Retry & fallback resilience engine | `resilience.py` (1s/2s/4s backoff on 429/5xx, immediate fallback on 401/exhaustion) + unit tests |
| **T7** | Chat orchestrator & JSON repair | `chat.py` (full turn pipeline, injection short-circuit, 1-step JSON repair) + unit tests |
| **T8** | Security & AST boundary tests | `tests/test_security.py`, `tests/test_boundaries.py` (S1–S8 verification) |
| **T9** | Streamlit UI & CLI demo runner | `src/chatbot/app.py`, `scripts/demo_cli.py`, `tests/test_app.py` (`AppTest`) |
| **T10** | Live Gemini verification (`.env`) | Headless live smoke run using `GEMINI_API_KEY` from `.env`, writes `docs/live_verification.md` |
| **T11** | Documentation & threat model | `README.md`, `THREAT_MODEL.md`, `docs/decisions.md`, `docs/EXPLAIN-PLAIN-ENGLISH.md` |
| **T12** | Release & GitHub push | Coverage check (`>=85%`), tag `v0.1.0`, push `main` and `v0.1.0` to GitHub |

---

## T0 (AGENT): create public GitHub repository `adwitiya-pandey/multi-provider-llm-chatbot`
1. In `~/projects/multi-provider-llm-chatbot`, run `git init` and `git branch -M main`.
2. Ensure `.gitignore` includes `.env`, `ONE-SHOT-PROMPT.txt`, `PROGRESS.md`, `.venv/`, `__pycache__/`, `*.db`, `logs/`.
3. Commit initial contract files (`AGENTS.md`, `SPEC.md`, `TASKS.md`, `docs/sdk_notes.md`, `.gitignore`, `.gitattributes`, `.editorconfig`, `.vscode/`, `.github/`):
   `git commit -m "docs: add scope contract (AGENTS, SPEC, TASKS)"`
4. Check if `adwitiya-pandey/multi-provider-llm-chatbot` exists on GitHub (`gh repo view adwitiya-pandey/multi-provider-llm-chatbot`); if not, create it publicly and push:
   `gh repo create adwitiya-pandey/multi-provider-llm-chatbot --public --source=. --remote=origin --push --description "Modular multi-provider LLM chatbot: Google GenAI, Anthropic & OpenAI SDK adapters, retry/fallback resilience, structured Pydantic outputs, token cost tracking, Streamlit UI"`
Accept: `git remote -v` points to `https://github.com/adwitiya-pandey/multi-provider-llm-chatbot` and `main` is pushed.

## T1 (AGENT): scaffold, CI, and SDK probe verification
1. Configure `pyproject.toml` (Python `>=3.12`, package `chatbot` in `src/chatbot/`, dependencies: `google-genai`, `anthropic`, `openai`, `pydantic`, `pydantic-settings`, `python-dotenv`, `streamlit`; dev: `pytest`, `pytest-cov`, `ruff`).
2. Create empty module stubs in `src/chatbot/` (`__init__.py`, `config.py`, `models.py`, `logging_setup.py`, `sanitize.py`, `prompts.py`, `memory.py`, `cost.py`, `providers.py`, `resilience.py`, `chat.py`, `app.py`).
3. Create `.env.example` (with `GEMINI_API_KEY=your-gemini-key-here`, `LLM_MODE=auto`, `SESSION_BUDGET_USD=0.50`), `LICENSE` (MIT, Adwitiya Pandey), and `.github/workflows/ci.yml` (runs `ruff check`, `ruff format --check`, and `pytest --cov=src/chatbot --cov-fail-under=85`).
4. Verify `docs/sdk_notes.md` against installed packages and add `tests/conftest.py` ensuring offline test isolation.
Accept: `uv sync && uv run ruff check . && uv run pytest -q` pass.

## T2 (AGENT): models, `.env` config, and metadata-only logging
1. Implement `src/chatbot/models.py` per SPEC 3 (`extra="forbid"`, `strict=True`).
2. Implement `src/chatbot/config.py` using `pydantic-settings` (`SettingsConfigDict(env_file=".env", extra="ignore")`) with `SecretStr` for keys and automatic mode resolution (`live` if `GEMINI_API_KEY` is non-empty, else `scripted`).
3. Implement `src/chatbot/logging_setup.py` emitting structured JSON with only allowed metadata keys (never prompt or reply text).
4. Write `tests/test_models.py`, `tests/test_config.py`, and `tests/test_logging.py`.
Accept: `uv run pytest tests/test_models.py tests/test_config.py tests/test_logging.py -q` passes.

## T3 (AGENT): input sanitization, injection detection, and prompt templates
1. Write `tests/test_sanitize.py` (12+ prompt injection positives, 8+ benign technical questions, control character stripping, 4,000-char cap, `<user_message>` wrapping) and `tests/test_prompts.py` (template loading, missing placeholder error, schema injection).
2. Implement `src/chatbot/sanitize.py`, `prompts/system_v1.md`, `prompts/repair_v1.md`, and `src/chatbot/prompts.py`.
Accept: `uv run pytest tests/test_sanitize.py tests/test_prompts.py -q` passes.

## T4 (AGENT): sliding-window multi-turn memory and token/cost tracker
1. Write `tests/test_memory.py` (turn limit eviction, token budget eviction, formatting to provider messages, clear) and `tests/test_cost.py` (per-model token pricing math, cumulative session totals, `$0.50` budget ceiling raising `BudgetExceededError`).
2. Implement `src/chatbot/memory.py` and `src/chatbot/cost.py`.
Accept: `uv run pytest tests/test_memory.py tests/test_cost.py -q` passes.

## T5 (AGENT): multi-provider SDK adapters (`google-genai`, `anthropic`, `openai`, `scripted`)
1. Implement `src/chatbot/providers.py` containing `GeminiProvider`, `AnthropicProvider`, `OpenAIProvider`, and `ScriptedProvider`, each accepting an optional injected `sdk_client` for offline unit testing and normalizing SDK exceptions into `ProviderError(code, provider, retryable)`.
2. Write `tests/test_providers.py` testing all four providers offline using fake SDK clients (`FakeGeminiClient`, `FakeAnthropicClient`, `FakeOpenAIClient`): verify request parameters, token usage extraction, and error code mapping (`429 -> retryable=True`, `503 -> retryable=True`, `401 -> retryable=False`).
Accept: `uv run pytest tests/test_providers.py -q` passes.

## T6 (AGENT): exponential backoff retry and automatic fallback router
1. Write `tests/test_resilience.py` using an injected fake clock/sleep list (`sleeps = []`):
   - Primary succeeds on attempt 1 (`retries_used=0, fallback_used=False`).
   - Primary fails twice with `429 RATE_LIMITED` then succeeds on attempt 3 (`sleeps == [1.0, 2.0]`, `retries_used=2, fallback_used=False`).
   - Primary fails 4 times with `503 SERVER_ERROR` (`sleeps == [1.0, 2.0, 4.0]`), router falls back to Secondary provider which succeeds (`fallback_used=True`, 5 total attempts recorded).
   - Primary fails with `401 AUTH_ERROR`, router immediately switches to Secondary with `0` retries on Primary (`sleeps == []`, `fallback_used=True`).
   - All providers fail -> raises `AllProvidersFailedError` with safe error codes.
2. Implement `src/chatbot/resilience.py`.
Accept: `uv run pytest tests/test_resilience.py -q` passes.

## T7 (AGENT): chat turn orchestrator and 1-step JSON repair
1. Write `tests/test_chat.py` covering: happy path (`StructuredReply` returned, memory updated, cost tracked); prompt-injection input short-circuited (`injection_flagged=True`, 0 provider calls); malformed JSON repaired on retry (`repair_used=True`); repair exhausted falls back to safe deterministic `StructuredReply`; session budget exceeded blocks call.
2. Implement `src/chatbot/chat.py`.
Accept: `uv run pytest tests/test_chat.py -q` passes.

## T8 (AGENT): security and AST import-boundary suite
1. Write `tests/test_boundaries.py` (AST scan proving `google.genai`, `anthropic`, and `openai` are imported ONLY in `src/chatbot/providers.py`, and banning `langchain*`, `llama_index*`, `litellm*`) and `tests/test_security.py` (verifying `.gitignore` has `.env`, `.env.example` has no real keys, config errors never leak keys).
Accept: `uv run pytest tests/test_boundaries.py tests/test_security.py -q` passes.

## T9 (AGENT): Streamlit UI and CLI demo script
1. Implement `src/chatbot/app.py` (sidebar with mode indicator `LIVE GEMINI` vs `SCRIPTED OFFLINE DEMO`, provider chain selector, session token & USD cost metrics out of `$0.50` budget, per-provider cost table, Clear Memory button; main chat view rendering `StructuredReply.answer` plus expandable `key_points`, `follow_up_questions`, `confidence`, and attempt/fallback trace badges).
2. Implement `scripts/demo_cli.py` running a 3-turn scripted demo conversation and printing a summary table.
3. Write `tests/test_app.py` using `streamlit.testing.v1.AppTest`.
Accept: `uv run pytest tests/test_app.py -q && uv run python scripts/demo_cli.py` pass.

## T10 (AGENT): live Gemini verification using `.env`
1. Write `scripts/live_smoke_test.py` which loads `.env` via `config.py`. If `GEMINI_API_KEY` is present in `.env`, it runs 2 live turns (`GeminiProvider("gemini-2.5-flash")`) and 1 simulated primary failure that falls back to `GeminiProvider("gemini-2.5-flash-lite")`, and writes the measured latency, token counts, and notional cost to `docs/live_verification.md` (if no `.env` key is set, it runs in `scripted` mode and records that).
2. Execute `uv run python scripts/live_smoke_test.py`.
Accept: `docs/live_verification.md` exists and contains zero secret values.

## T11 (AGENT): README, threat model, decisions, and plain-English guide
1. Write a comprehensive `README.md` (architecture diagram, provider fallback table, quickstart for both zero-key scripted mode and `.env` Gemini live mode, security summary, test coverage summary), `THREAT_MODEL.md` (STRIDE table mapped to S1–S8), `docs/decisions.md`, and `docs/EXPLAIN-PLAIN-ENGLISH.md`.
Accept: All links resolve and `git grep -i "AI""za"` is empty.

## T12 (AGENT): final verification, tag `v0.1.0`, and push to GitHub
1. Run `uv run ruff check . && uv run ruff format --check . && uv run pytest -q --cov=src/chatbot --cov-fail-under=85`.
2. Confirm `git status` is clean and `.env` is NOT tracked (`git ls-files | grep -E '^\.env$'` is empty).
3. Commit all work, create tag `git tag -a v0.1.0 -m "v0.1.0 release"`, and push both `main` and `v0.1.0` to `origin` (`https://github.com/adwitiya-pandey/multi-provider-llm-chatbot`).
Accept: CI checks pass locally and `main` + `v0.1.0` are pushed to GitHub.
