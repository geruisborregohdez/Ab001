"""
Agent chat page — ChatGPT-style interface.
Default landing page of the app.
"""
import os
import uuid

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

st.set_page_config(
    page_title="Ab001 — Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Session state ─────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Ab001")
    st.page_link("app.py", label="Agent Chat", icon="🤖")
    st.page_link("pages/1_Data_Manager.py", label="Data Manager", icon="📋")
    st.divider()

    if st.button("New conversation", use_container_width=True):
        try:
            requests.delete(
                f"{BACKEND_URL}/api/agent/chat/{st.session_state.session_id}",
                timeout=5,
            )
        except Exception:
            pass
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption(f"Session: `{st.session_state.session_id[:8]}…`")

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Business Assistant")
st.caption("Ask me to create customers, log services, generate invoices, or send them to QuickBooks.")
st.divider()

# ── Chat messages ─────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("e.g. Create a customer named John Doe, phone 555-1234..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/api/agent/chat",
                    json={"message": prompt, "session_id": st.session_state.session_id},
                    timeout=60,
                )
                resp.raise_for_status()
                answer = resp.json()["response"]
            except Exception as exc:
                answer = f"Error contacting backend: {exc}"

        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
