"""
app.py — Phase 3: Streamlit Chat UI with Session Memory

Construction Knowledge Assistant — chat-style RAG interface.
Conversation history is stored per-session in Redis (1hr TTL).
Repeated or paraphrased questions are served from the semantic cache.

Run:   streamlit run app.py
"""

import uuid
import streamlit as st

from config import EMBEDDING_MODEL, LLM_MODEL, LLM_BACKEND
from pipeline import ask_question
from memory.redis_client import redis_available

# ── Page configuration ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Construction Knowledge Assistant",
    page_icon="🏗️",
    layout="wide",
)

# ── Source document list ───────────────────────────────────────────────────────
SOURCE_DOCUMENTS = [
    "gtm_construction_safety_manual.pdf",
    "txdot_bridge_inspection_manual.pdf",
    "wsdot_construction_manual.pdf",
    "montana_dot_project_report.pdf",
    "osha_construction_safety_guide.pdf",
]

# ══════════════════════════════════════════════════════════════════════════════
# Session state initialisation
# Streamlit re-runs the entire script on every interaction.
# st.session_state persists data across those re-runs.
# ══════════════════════════════════════════════════════════════════════════════

# Generate a unique session ID for this browser tab (persists until refresh)
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Local chat history for display (mirrors what's stored in Redis)
# Format: [{"role": "user"|"assistant", "content": str, "sources": [], "chunks": [], "from_cache": bool}]
if "messages" not in st.session_state:
    st.session_state.messages = []

# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("🏗️ Construction Assistant")
    st.divider()

    # ── Redis status indicator ─────────────────────────────────────────────────
    redis_on = redis_available()
    if redis_on:
        st.success("🟢 Redis Connected", icon=None)
        st.caption("Session memory & semantic cache active")
    else:
        st.warning("🟡 Redis Offline", icon=None)
        st.caption("Running without memory/cache")

    st.divider()

    # ── Active config ──────────────────────────────────────────────────────────
    st.markdown("**Active Configuration**")
    st.markdown(
        f"""
| Setting | Value |
|---|---|
| Embeddings | `{EMBEDDING_MODEL}` |
| LLM | `{LLM_MODEL}` |
| Backend | `{LLM_BACKEND}` |
"""
    )

    st.divider()

    # ── Source documents ───────────────────────────────────────────────────────
    st.markdown("**Source Documents**")
    for doc in SOURCE_DOCUMENTS:
        st.markdown(f"- `{doc}`")

    st.divider()

    # ── Session info ───────────────────────────────────────────────────────────
    st.markdown("**Session**")
    st.code(st.session_state.session_id[:8] + "...", language=None)
    st.caption(f"{len(st.session_state.messages) // 2} exchange(s) this session")

    # ── Clear chat button ──────────────────────────────────────────────────────
    if st.button("🗑️ Clear Chat", use_container_width=True):
        # Clear local display
        st.session_state.messages = []
        # Clear Redis session history
        if redis_on:
            from memory.session_store import clear_session
            clear_session(st.session_state.session_id)
        # New session ID so old cache doesn't interfere
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.caption("💡 Try asking about bridge inspection, PPE requirements, or fall protection.")

# ══════════════════════════════════════════════════════════════════════════════
# Main Chat Area
# ══════════════════════════════════════════════════════════════════════════════
st.title("Construction Knowledge Assistant 🏗️")
st.caption(
    f"Powered by **{EMBEDDING_MODEL}** embeddings · **{LLM_MODEL}** · "
    f"Backend: **{LLM_BACKEND}**"
)
st.divider()

# ── Render existing conversation history ──────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Show cache badge for assistant messages that were cache hits
        if msg["role"] == "assistant" and msg.get("from_cache"):
            st.caption("⚡ Served from semantic cache")

        # Show sources for assistant messages
        if msg["role"] == "assistant" and msg.get("sources"):
            with st.expander(f"📄 View {len(msg['sources'])} source chunk(s)"):
                for i, (chunk_text, source_info) in enumerate(
                    zip(msg["chunks"], msg["sources"]), start=1
                ):
                    st.markdown(
                        f"**Rank {i} — {source_info['file']} — Page {source_info['page']}**"
                    )
                    st.markdown(chunk_text)
                    if i < len(msg["sources"]):
                        st.divider()

# ── Chat input (always pinned to bottom by Streamlit) ─────────────────────────
if prompt := st.chat_input("Ask a question about the construction documents..."):

    # 1. Show user message immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Run pipeline and show assistant response
    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching documents..."):
            try:
                result = ask_question(
                    query=prompt,
                    session_id=st.session_state.session_id,
                )

                answer     = result["answer"]
                sources    = result["sources"]
                chunks     = result["chunks"]
                from_cache = result.get("from_cache", False)

                # Display answer
                if answer.startswith("Error:"):
                    st.error(answer)
                else:
                    st.markdown(answer)

                # Cache hit badge
                if from_cache:
                    st.caption("⚡ Served from semantic cache")

                # Source chunks
                if sources:
                    with st.expander(f"📄 View {len(sources)} source chunk(s)"):
                        for i, (chunk_text, source_info) in enumerate(
                            zip(chunks, sources), start=1
                        ):
                            st.markdown(
                                f"**Rank {i} — {source_info['file']} — Page {source_info['page']}**"
                            )
                            st.markdown(chunk_text)
                            if i < len(sources):
                                st.divider()

            except Exception as exc:
                answer, sources, chunks, from_cache = f"Error: {exc}", [], [], False
                st.error(answer)

    # 3. Save assistant message to local session state for re-renders
    st.session_state.messages.append({
        "role":       "assistant",
        "content":    answer,
        "sources":    sources,
        "chunks":     chunks,
        "from_cache": from_cache,
    })
