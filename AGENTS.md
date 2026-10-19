# AGENTS.md — multi-provider-llm-chatbot

> **AUTONOMOUS END-TO-END EXECUTION RULE (SINGLE-CHAT WORKFLOW)**:
> Execute **all tasks in `TASKS.md` back-to-back from `T0` through `T12` (`v0.1.0` GitHub push)** in a single continuous run.
> - **Do NOT stop after individual tasks** to wait for human PR merges. Commit each task cleanly with Conventional Commits (`Refs: T<N>`), merge branches into `main` automatically, update `PROGRESS.md`, and continue straight to the next task.
> - **Write 100% of the code yourself** and explain every completed module in `docs/EXPLAIN-PLAIN-ENGLISH.md`.
> - **API Keys**: Load `GEMINI_API_KEY` automatically from the project's local `.env` file (gitignored, loaded via `python-dotenv` / `pydantic-settings`). Never print or commit `.env`.

Read `SPEC.md` (the contract), `TASKS.md`, and `docs/sdk_notes.md` before writing code.

## What this is
A modular, production-tested multi-provider LLM chatbot in Python (`github.com/adwitiya-pandey/multi-provider-llm-chatbot`) built on the official **Google GenAI (`google-genai`)**, **Anthropic (`anthropic`)**, and **OpenAI (`openai`)** SDKs. It features strict Pydantic input/output validation, exponential backoff retries, automatic provider/model fallback (`primary -> secondary -> offline scripted`), sliding-window multi-turn conversation memory, structured JSON output parsing with automatic repair, file-based prompt templates, per-turn and cumulative token/USD cost tracking, and a Streamlit UI; managed with `uv` and tested with `pytest`.

## Environment and commands
- Work in WSL2 Ubuntu under `~/projects/multi-provider-llm-chatbot` (never under `/mnt/c` or `/mnt/d`). CI runs Linux. Use `pathlib`; Line endings are LF (`.gitattributes`).
- Install: `uv sync`
- Check: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`
- Run the app: `uv run streamlit run src/chatbot/app.py`
- Run each task's acceptance command from `TASKS.md` before committing.

## Gotchas that will bite you
1. **Live vs. Mocked Provider Keys (`.env` Rule)**:
   - The owner ONLY has a Google Gemini API key (`GEMINI_API_KEY` stored in the gitignored `.env` file).
   - **No `ANTHROPIC_API_KEY` and no `OPENAI_API_KEY` exist in `.env`.**
   - In live mode (`LLM_MODE=live`), the default fallback chain is `gemini-primary` (`gemini-2.5-flash`) -> `gemini-fallback` (`gemini-2.5-flash-lite`) via `google-genai`, so live runs work 100% with only `GEMINI_API_KEY`.
   - The `AnthropicProvider` (`anthropic` SDK) and `OpenAIProvider` (`openai` SDK) adapters must be fully implemented in `src/chatbot/providers.py` and tested 100% offline in `tests/test_providers.py` and `tests/test_resilience.py` using injected fake/mocked SDK client objects (`FakeAnthropicClient`, `FakeOpenAIClient`, `FakeGeminiClient`).
2. **Default Offline Demo Mode (`LLM_MODE=scripted`)**:
   - When no `.env` or `GEMINI_API_KEY` is present (such as when an interviewer clones the repo or in CI), `config.py` defaults to `LLM_MODE=scripted`, which uses `ScriptedProvider` so `uv run streamlit run src/chatbot/app.py` works out-of-the-box with zero keys. When `GEMINI_API_KEY` is present in `.env`, `LLM_MODE` automatically defaults to `live` unless overridden.
3. **Provider SDK Isolation**:
   - Only `src/chatbot/providers.py` may import `google.genai`, `anthropic`, or `openai`. No LangChain, LlamaIndex, or LiteLLM wrappers are allowed anywhere (`tests/test_boundaries.py` enforces this via AST inspection).
4. **Retry vs. Fallback Contract (`resilience.py`)**:
   - Transient errors (`HTTP 429`, `500`, `502`, `503`, `504`, network timeouts) are retried up to `max_retries=3` times on the *current* provider using exponential backoff (`1.0s`, `2.0s`, `4.0s`) via an injectable `sleep` function (so tests run in 0ms).
   - Permanent client errors (`HTTP 400`, `401`, `403`, missing API key) are **not** retried on the same provider; `resilience.py` immediately records the failure reason and falls back to the next provider in the chain.
   - If all configured providers fail, raise a typed `AllProvidersFailedError` containing the sanitized error code per provider (never echoing API keys).
5. **Structured JSON Output & 1-Step Repair (`chat.py`)**:
   - Every LLM call requests a JSON object matching `StructuredReply` (`answer: str`, `category: Literal["general", "technical", "clarification", "refusal"]`, `key_points: list[str]`, `follow_up_questions: list[str]`, `confidence: float`).
   - Parse with `StructuredReply.model_validate_json(raw_text)`. If validation or JSON parsing fails, make **at most 1 repair call** passing the validation error summary (field names only, never raw user secrets). If the repair call also fails, return a deterministic fallback `StructuredReply` with `status="parse_repaired_fallback"`.
6. **Streamlit State & Plain-Text Rendering**:
   - Streamlit re-runs `app.py` on every interaction. Keep conversation memory, turn history, and cumulative cost strictly inside `st.session_state`. Render model text safely without `unsafe_allow_html=True`.
7. **Secrets & Logging Safety**:
   - Never print, log, or commit `.env` or any API key value. Structured JSON logs (`logging_setup.py`) record metadata only (`turn_id`, `provider`, `model`, `retries_used`, `fallback_used`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `status`) — never raw user prompts or model replies.

## Work style: Autonomous End-to-End Execution
- Execute tasks `T0` through `T12` sequentially in one continuous run.
- After each task passes its acceptance command and `ruff`, commit with Conventional Commits (`feat(providers): add Gemini, Anthropic, and OpenAI SDK adapters`, trailer `Refs: T4`), merge into `main`, check off the task in `PROGRESS.md`, append a plain-English explanation to `docs/EXPLAIN-PLAIN-ENGLISH.md`, and immediately start the next task.
- In `T0`, create the public GitHub repository `adwitiya-pandey/multi-provider-llm-chatbot` via `gh repo create` (or link `origin` if already created).
- In `T12`, push `main` and tag `v0.1.0` to `origin`.
