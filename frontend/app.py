"""
Streamlit chat UI for Ab001.

Talks to the FastAPI backend at BACKEND_URL (default http://backend:8000).
"""
import os
import uuid

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

st.set_page_config(page_title="Ab001 Business Assistant", page_icon="🏢", layout="wide")

# ── Session state init ───────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Ab001")
    st.caption("Multiservice Business Manager")
    st.divider()

    if st.button("New conversation", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.subheader("Quick view")

    tab = st.radio("Show", ["Customers", "Services", "Invoices"], label_visibility="collapsed")

    try:
        if tab == "Customers":
            resp = requests.get(f"{BACKEND_URL}/api/customers", timeout=5)
            customers = resp.json()
            if customers:
                for c in customers:
                    st.write(f"**{c['name']}** — {c.get('phone', '-')}")
            else:
                st.caption("No customers yet.")

        elif tab == "Services":
            resp = requests.get(f"{BACKEND_URL}/api/services", timeout=5)
            services = resp.json()
            if services:
                for s in services:
                    badge = {"pending": "🟡", "in_progress": "🔵", "completed": "🟢"}.get(s["status"], "")
                    st.write(f"{badge} {s['name']} — ${s['price']}")
            else:
                st.caption("No services yet.")

        elif tab == "Invoices":
            resp = requests.get(f"{BACKEND_URL}/api/invoices", timeout=5)
            invoices = resp.json()
            if invoices:
                for i in invoices:
                    badge = {"draft": "📝", "sent": "📤", "paid": "✅"}.get(i["status"], "")
                    st.write(f"{badge} {i['invoice_number']} — ${i['total_amount']}")
            else:
                st.caption("No invoices yet.")
    except Exception:
        st.caption("Backend unavailable.")

    st.divider()
    st.caption(f"Session: `{st.session_state.session_id[:8]}…`")


# ── Main chat area ────────────────────────────────────────────────────────────
st.title("Business Assistant")
st.caption("Ask me to create customers, log services, generate invoices, or send them to QuickBooks.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

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
