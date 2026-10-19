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
