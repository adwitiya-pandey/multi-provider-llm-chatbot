"""Streamlit Web Application for Multi-Provider LLM Chatbot (SPEC 1, SPEC 2, Gotcha 6)."""

import pandas as pd
import streamlit as st

from chatbot.chat import ChatOrchestrator
from chatbot.config import get_settings
from chatbot.cost import BudgetExceededError, CostTracker
from chatbot.memory import ConversationMemory
from chatbot.models import TurnResult, UserTurnInput
from chatbot.providers import GeminiProvider, ScriptedProvider
from chatbot.resilience import ResilientRouter


def init_session_state() -> None:
    """Initializes persistent session state objects."""
    if "memory" not in st.session_state:
        st.session_state.memory = ConversationMemory(max_turns=10, max_estimated_tokens=6000)
    if "cost_tracker" not in st.session_state:
        settings = get_settings()
        st.session_state.cost_tracker = CostTracker(session_budget_usd=settings.SESSION_BUDGET_USD)
    if "turn_history" not in st.session_state:
        st.session_state.turn_history = []


def create_router(chain_option: str) -> ResilientRouter:
    """Constructs provider router based on UI selection and environment capabilities."""
    settings = get_settings()

    if chain_option == "Gemini Live Primary -> Fallback" and settings.has_gemini_key():
        key = settings.GEMINI_API_KEY.get_secret_value()  # type: ignore[union-attr]
        primary = GeminiProvider(model_name=settings.PRIMARY_MODEL_GEMINI, api_key=key)
        fallback = GeminiProvider(model_name=settings.FALLBACK_MODEL_GEMINI, api_key=key)
        scripted = ScriptedProvider()
        return ResilientRouter(providers=[primary, fallback, scripted])

    # Default to Scripted offline provider
    return ResilientRouter(providers=[ScriptedProvider()])


def render_sidebar() -> str:
    """Renders the configuration and telemetry sidebar."""
    settings = get_settings()
    st.sidebar.title("⚙️ System Control")

    # Mode Indicator Badge
    if settings.resolved_mode == "live":
        st.sidebar.success("🟢 MODE: LIVE GEMINI")
        chain_choices = [
            "Gemini Live Primary -> Fallback",
            "Scripted Offline Demo",
        ]
    else:
        st.sidebar.info("🔵 MODE: SCRIPTED OFFLINE DEMO")
        chain_choices = ["Scripted Offline Demo"]

    chain_option = st.sidebar.selectbox("Active Provider Chain", chain_choices, index=0)

    # Financial & Token Metrics
    st.sidebar.divider()
    st.sidebar.subheader("📊 Session Telemetry")

    tracker: CostTracker = st.session_state.cost_tracker
    summary = tracker.get_summary()

    spent = summary["total_cost_usd"]
    budget = summary["budget_usd"]
    pct = min(1.0, spent / budget) if budget > 0 else 0.0

    st.sidebar.metric(
        label="Budget Consumption",
        value=f"${spent:.5f}",
        delta=f"Limit: ${budget:.2f}",
        delta_color="off",
    )
    st.sidebar.progress(pct, text=f"{pct * 100:.1f}% of budget used")

    c1, c2 = st.sidebar.columns(2)
    with c1:
        st.metric("Total Turns", summary["total_turns"])
    with c2:
        st.metric("Total Tokens", summary["total_tokens"])

    memory: ConversationMemory = st.session_state.memory
    st.sidebar.caption(
        f"context used: {memory.estimated_tokens} / {memory.max_estimated_tokens} estimated tokens "
        "(approximate for non-OpenAI providers)"
    )

    # Per-provider breakdown table
    cost_data = [
        {"Provider": p, "Cost (USD)": f"${cost:.5f}"}
        for p, cost in summary["cost_by_provider"].items()
    ]
    if cost_data:
        st.sidebar.markdown("**Cost by Provider**")
        st.sidebar.dataframe(pd.DataFrame(cost_data), hide_index=True)

    # Clear Session Memory
    st.sidebar.divider()
    if st.sidebar.button("🧹 Clear Conversation Memory", use_container_width=True):
        st.session_state.memory.clear()
        st.session_state.turn_history.clear()
        st.rerun()

    return chain_option


def render_turn_result(turn: TurnResult, user_prompt: str) -> None:
    """Renders a single conversational turn in the chat view."""
    # User message
    with st.chat_message("user"):
        st.write(user_prompt)

    # Assistant message
    with st.chat_message("assistant"):
        # Status Badges
        badges = [
            f"🏷️ `{turn.reply.category.upper()}`",
            f"🤖 `{turn.provider_used}` ({turn.model_used})",
            f"⏱️ `{turn.usage.total_tokens} tokens` (${turn.usage.cost_usd:.5f})",
        ]
        if turn.fallback_used:
            badges.append("⚠️ **FALLBACK ACTIVE**")
        if turn.repair_used:
            badges.append("🔧 **JSON REPAIRED**")
        if turn.injection_flagged:
            badges.append("🛡️ **INJECTION BLOCKED**")

        st.caption(" • ".join(badges))

        # Main Answer
        st.write(turn.reply.answer)

        # Expandable Structured Details
        with st.expander("🔍 Structured Metadata & Inspection", expanded=False):
            st.markdown(f"**Confidence Score**: `{turn.reply.confidence * 100:.1f}%`")

            if turn.reply.key_points:
                st.markdown("**Key Points:**")
                for pt in turn.reply.key_points:
                    st.markdown(f"- {pt}")

            if turn.reply.follow_up_questions:
                st.markdown("**Suggested Follow-Ups:**")
                for q in turn.reply.follow_up_questions:
                    st.markdown(f"- *{q}*")

            if turn.attempts:
                st.markdown("**Provider Attempt Trace:**")
                attempt_rows = [
                    {
                        "Attempt": a.attempt_number,
                        "Provider": a.provider,
                        "Model": a.model,
                        "Success": "✅ Yes" if a.success else "❌ No",
                        "Error": a.error_code or "—",
                        "Latency (ms)": f"{a.latency_ms:.1f}",
                    }
                    for a in turn.attempts
                ]
                st.dataframe(pd.DataFrame(attempt_rows), hide_index=True)


def main() -> None:
    """Main application entrypoint."""
    st.set_page_config(
        page_title="Multi-Provider LLM Chatbot",
        page_icon="🤖",
        layout="wide",
    )

    init_session_state()
    chain_option = render_sidebar()

    st.title("🤖 Multi-Provider LLM Chatbot")
    st.markdown(
        "Production-tested multi-provider chatbot with official SDK adapters, strict Pydantic "
        "validation, exponential backoff retries, automatic fallback, and token cost accounting."
    )

    # Display historical turns
    for user_text, turn_res in st.session_state.turn_history:
        render_turn_result(turn_res, user_text)

    # Chat user input
    user_prompt = st.chat_input("Ask a question about AI or data engineering...")

    if user_prompt:
        router = create_router(chain_option)
        orchestrator = ChatOrchestrator(
            router=router,
            memory=st.session_state.memory,
            cost_tracker=st.session_state.cost_tracker,
        )

        try:
            inp = UserTurnInput(text=user_prompt)
            turn_result = orchestrator.turn(inp)
            st.session_state.turn_history.append((user_prompt, turn_result))
            st.rerun()
        except BudgetExceededError as exc:
            st.error(f"🛑 Budget Guardrail Exceeded: {exc}")
        except Exception as exc:
            st.error(f"❌ Error processing request: {exc}")


if __name__ == "__main__":
    main()
