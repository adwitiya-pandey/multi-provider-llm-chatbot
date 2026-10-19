# Multi-Provider LLM Chatbot

A modular, production-tested multi-provider LLM chatbot in Python built on the official **Google GenAI (`google-genai`)**, **Anthropic (`anthropic`)**, and **OpenAI (`openai`)** SDKs.

## Features
- **Official SDK Adapters**: Clean separation of concerns with direct SDK adapters for Google GenAI, Anthropic, and OpenAI, plus an offline Scripted demo adapter.
- **Pydantic Validation**: Strict input sanitization and structured JSON output validation (`StructuredReply`).
- **Resilience Engine**: Exponential backoff retries (`1.0s, 2.0s, 4.0s`) on transient errors (HTTP 429, 5xx) with automatic provider fallback on auth failure or retry exhaustion.
- **Self-Healing Output**: 1-step automated JSON repair retry if a provider returns non-conforming JSON.
- **Multi-Turn Memory**: Sliding-window conversation memory with token and turn count limits.
- **Cost & Token Accounting**: Real-time per-turn and session USD cost tracking against a hard spending ceiling.
- **Streamlit Web UI & CLI**: User-friendly web interface and scriptable CLI runner.
- **Managed with `uv` & tested with `pytest`**: 100% offline unit test suite with 85%+ code coverage.
