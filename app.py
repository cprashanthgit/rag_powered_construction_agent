"""
app.py — Phase 4: Full Streamlit UI connected to FastAPI

Single entry point showing ALL project features:
  - Login with email/password (JWT auth via FastAPI)
  - Role badge (public / inspector / admin)
  - Chat interface with session memory (Redis)
  - Semantic cache hit indicator (⚡)
  - 👍 / 👎 feedback buttons on every answer
  - System status panel (API, Redis, PostgreSQL)
  - Source chunk expanders

Architecture:
  app.py  →  POST /auth/token    (login)
  app.py  →  POST /query/sync    (ask question, logs to PostgreSQL)
  app.py  →  POST /feedback      (rate an answer)
  app.py  →  GET  /health        (system status in sidebar)

Run both processes:
  Terminal 1:  uvicorn api:app --host 0.0.0.0 --port 8000 --reload
  Terminal 2:  streamlit run app.py
"""

import uuid
import httpx
import streamlit as st

# ── Config ─────────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"
TIMEOUT  = 120  # seconds — long enough for a cold-start LLM response

# ── Page setup ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Construction Knowledge Assistant",
    page_icon="🏗️",
    layout="wide",
)

SOURCE_DOCUMENTS = [
    "gtm_construction_safety_manual.pdf",
    "txdot_bridge_inspection_manual.pdf",
    "wsdot_construction_manual.pdf",
    "montana_dot_project_report.pdf",
    "osha_construction_safety_guide.pdf",
]

# ══════════════════════════════════════════════════════════════════════════════
# Session state initialisation
# ══════════════════════════════════════════════════════════════════════════════
if "session_id"   not in st.session_state:
    st.session_state.session_id   = str(uuid.uuid4())
if "messages"     not in st.session_state:
    st.session_state.messages     = []       # chat history for display
if "jwt_token"    not in st.session_state:
    st.session_state.jwt_token    = None     # None = not logged in
if "user_email"   not in st.session_state:
    st.session_state.user_email   = None
if "user_role"    not in st.session_state:
    st.session_state.user_role    = None
if "login_error"  not in st.session_state:
    st.session_state.login_error  = ""


# ══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ══════════════════════════════════════════════════════════════════════════════

def auth_headers() -> dict:
    """Return Authorization header if logged in, empty dict if anonymous."""
    if st.session_state.jwt_token:
        return {"Authorization": f"Bearer {st.session_state.jwt_token}"}
    return {}


def get_health() -> dict:
    """Call GET /health and return the response dict, or None on failure."""
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def do_login(email: str, password: str) -> bool:
    """POST /auth/token. Returns True on success, sets error on failure."""
    try:
        r = httpx.post(
            f"{API_BASE}/auth/token",
            json={"email": email, "password": password},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            st.session_state.jwt_token   = data["access_token"]
            st.session_state.user_email  = data["email"]
            st.session_state.user_role   = data["role"]
            st.session_state.login_error = ""
            return True
        else:
            st.session_state.login_error = r.json().get("detail", "Login failed")
            return False
    except Exception as e:
        st.session_state.login_error = f"Cannot reach API: {e}"
        return False


def do_query(question: str) -> dict:
    """POST /query/sync and return the result dict."""
    r = httpx.post(
        f"{API_BASE}/query/sync",
        json={"question": question, "session_id": st.session_state.session_id},
        headers=auth_headers(),
        timeout=TIMEOUT,
    )
    if r.status_code == 200:
        return r.json()
    raise Exception(r.json().get("detail", f"API error {r.status_code}"))


def do_feedback(query_id: str, rating: int) -> None:
    """POST /feedback — fire and forget."""
    try:
        httpx.post(
            f"{API_BASE}/feedback",
            json={"query_id": query_id, "rating": rating, "comment": ""},
            headers=auth_headers(),
            timeout=5,
        )
    except Exception:
        pass  # feedback is non-critical


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("🏗️ Construction Assistant")
    st.divider()

    # ── System Status ──────────────────────────────────────────────────────────
    health = get_health()
    if health is None:
        st.error("🔴 API Offline")
        st.caption("Start the API: `uvicorn api:app --port 8000 --reload`")
    else:
        st.success("🟢 API Online", icon=None)
        col1, col2 = st.columns(2)
        with col1:
            if health.get("redis_connected"):
                st.success("Redis ✓", icon=None)
            else:
                st.warning("Redis ✗", icon=None)
        with col2:
            if health.get("postgres_connected"):
                st.success("PostgreSQL ✓", icon=None)
            else:
                st.warning("PostgreSQL ✗", icon=None)

        st.caption(
            f"LLM: `{health.get('llm_backend')}` · "
            f"Vectors: `{health.get('vector_backend')}`"
        )

    st.divider()

    # ── Login / User panel ─────────────────────────────────────────────────────
    if st.session_state.jwt_token is None:
        # Not logged in — show login form
        st.markdown("**🔐 Login**")
        st.caption("Login to identify your role and enable query logging.")

        with st.form("login_form", clear_on_submit=False):
            email    = st.text_input("Email",    placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            if do_login(email, password):
                st.rerun()

        if st.session_state.login_error:
            st.error(st.session_state.login_error)

        st.caption("No account? Queries still work anonymously as **public** role.")

    else:
        # Logged in — show user info
        ROLE_COLORS = {
            "admin":    "🔴",
            "inspector":"🟡",
            "public":   "🟢",
        }
        role  = st.session_state.user_role
        icon  = ROLE_COLORS.get(role, "⚪")
        st.success(f"✅ Logged in", icon=None)
        st.markdown(f"**{st.session_state.user_email}**")
        st.markdown(f"Role: {icon} `{role}`")

        if st.button("Logout", use_container_width=True):
            for key in ["jwt_token", "user_email", "user_role", "messages", "session_id"]:
                st.session_state[key] = None if "token" in key or "email" in key or "role" in key else \
                                        [] if key == "messages" else str(uuid.uuid4())
            st.rerun()

    st.divider()

    # ── Source Documents ───────────────────────────────────────────────────────
    st.markdown("**Source Documents**")
    for doc in SOURCE_DOCUMENTS:
        st.markdown(f"- `{doc}`")

    st.divider()

    # ── Session controls ───────────────────────────────────────────────────────
    st.caption(f"Session: `{st.session_state.session_id[:8]}...`")
    st.caption(f"{len(st.session_state.messages) // 2} exchange(s) this session")

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages   = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.caption("💡 Ask about PPE, fall protection, bridge inspection, or safety audits.")


# ══════════════════════════════════════════════════════════════════════════════
# Main Chat Area
# ══════════════════════════════════════════════════════════════════════════════
st.title("Construction Knowledge Assistant 🏗️")

if health is None:
    st.warning(
        "⚠️ The API is not running. Please start it first:\n\n"
        "```bash\nuvicorn api:app --host 0.0.0.0 --port 8000 --reload\n```"
    )
    st.stop()

if st.session_state.jwt_token:
    role = st.session_state.user_role
    ROLE_COLORS = {"admin": "🔴", "inspector": "🟡", "public": "🟢"}
    st.caption(
        f"Logged in as **{st.session_state.user_email}** · "
        f"Role: {ROLE_COLORS.get(role,'⚪')} `{role}` · "
        f"All queries logged to PostgreSQL"
    )
else:
    st.caption("Anonymous access · Role: 🟢 `public` · [Login in sidebar to enable query logging]")

st.divider()

# ── Render existing conversation ───────────────────────────────────────────────
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant":
            # Cache hit badge
            if msg.get("from_cache"):
                st.caption("⚡ Served from semantic cache")

            # Feedback buttons (only if we have a query_id)
            if msg.get("query_id"):
                qid = msg["query_id"]
                fb_key = f"fb_{qid}"
                if fb_key not in st.session_state:
                    st.session_state[fb_key] = None

                if st.session_state[fb_key] is None:
                    col1, col2, col3 = st.columns([1, 1, 8])
                    with col1:
                        if st.button("👍", key=f"up_{idx}_{qid}"):
                            do_feedback(qid, 1)
                            st.session_state[fb_key] = "up"
                            st.rerun()
                    with col2:
                        if st.button("👎", key=f"dn_{idx}_{qid}"):
                            do_feedback(qid, -1)
                            st.session_state[fb_key] = "down"
                            st.rerun()
                elif st.session_state[fb_key] == "up":
                    st.caption("✅ Thanks for the feedback!")
                else:
                    st.caption("📝 Thanks — we'll work on improving this.")

            # Source chunks
            if msg.get("sources"):
                with st.expander(f"📄 View {len(msg['sources'])} source chunk(s)"):
                    for i, (chunk, src) in enumerate(zip(msg["chunks"], msg["sources"]), 1):
                        st.markdown(f"**Rank {i} — {src['file']} — Page {src['page']}**")
                        st.markdown(chunk)
                        if i < len(msg["sources"]):
                            st.divider()

# ── Chat input ─────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask a question about the construction documents..."):

    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get answer from API
    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching documents..."):
            try:
                result     = do_query(prompt)
                answer     = result["answer"]
                sources    = result.get("sources", [])
                chunks     = result.get("chunks",  [])
                from_cache = result.get("from_cache", False)
                query_id   = result.get("query_id")      # may be None

                st.markdown(answer)

                if from_cache:
                    st.caption("⚡ Served from semantic cache")

                if query_id:
                    fb_key = f"fb_{query_id}"
                    st.session_state[fb_key] = None
                    col1, col2, col3 = st.columns([1, 1, 8])
                    with col1:
                        if st.button("👍", key=f"up_new_{query_id}"):
                            do_feedback(query_id, 1)
                            st.session_state[fb_key] = "up"
                            st.rerun()
                    with col2:
                        if st.button("👎", key=f"dn_new_{query_id}"):
                            do_feedback(query_id, -1)
                            st.session_state[fb_key] = "down"
                            st.rerun()

                if sources:
                    with st.expander(f"📄 View {len(sources)} source chunk(s)"):
                        for i, (chunk, src) in enumerate(zip(chunks, sources), 1):
                            st.markdown(f"**Rank {i} — {src['file']} — Page {src['page']}**")
                            st.markdown(chunk)
                            if i < len(sources):
                                st.divider()

            except Exception as exc:
                answer, sources, chunks, from_cache, query_id = (
                    f"Error: {exc}", [], [], False, None
                )
                st.error(answer)

    # Save to session state
    st.session_state.messages.append({
        "role":       "assistant",
        "content":    answer,
        "sources":    sources,
        "chunks":     chunks,
        "from_cache": from_cache,
        "query_id":   query_id,
    })
