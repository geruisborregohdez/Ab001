"""
Data Manager page — traditional CRUD UI for customers, services, and invoices.
"""
import os

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

st.set_page_config(
    page_title="Ab001 — Data Manager",
    page_icon="📋",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Ab001")
    st.page_link("app.py", label="Agent Chat", icon="🤖")
    st.page_link("pages/1_Data_Manager.py", label="Data Manager", icon="📋")


def api_get(path: str) -> list | dict | None:
    try:
        r = requests.get(f"{BACKEND_URL}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None


def api_post(path: str, payload: dict) -> dict | None:
    try:
        r = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None


def api_patch(path: str, payload: dict) -> dict | None:
    try:
        r = requests.patch(f"{BACKEND_URL}{path}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None


def api_delete(path: str) -> bool:
    try:
        r = requests.delete(f"{BACKEND_URL}{path}", timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Request failed: {e}")
        return False


# ── Page ──────────────────────────────────────────────────────────────────────
st.title("Data Manager")
st.caption("Directly create and manage customers, services, and invoices.")
st.divider()

tab_customers, tab_services, tab_invoices = st.tabs(["Customers", "Services", "Invoices"])


# ── Customers ─────────────────────────────────────────────────────────────────
with tab_customers:
    col_list, col_form = st.columns([3, 2], gap="large")

    with col_list:
        st.subheader("All Customers")
        if st.button("Refresh", key="refresh_customers"):
            st.rerun()

        customers = api_get("/api/customers") or []
        if customers:
            for c in customers:
                with st.expander(f"**{c['name']}** — {c.get('email', '—')}"):
                    cols = st.columns(2)
                    cols[0].write(f"**Phone:** {c.get('phone', '—')}")
                    cols[1].write(f"**ID:** {c['id']}")
                    addr = ", ".join(filter(None, [
                        c.get("address_street"), c.get("address_city"),
                        c.get("address_state"), c.get("address_zip"),
                    ]))
                    if addr:
                        st.write(f"**Address:** {addr}")

                    confirm_key = f"delete_confirm_{c['id']}"
                    if st.session_state.get(confirm_key):
                        st.warning(f"Delete **{c['name']}**? This cannot be undone.")
                        btn_cols = st.columns(2)
                        if btn_cols[0].button("Yes, delete", key=f"delete_yes_{c['id']}", type="primary"):
                            if api_delete(f"/api/customers/{c['id']}"):
                                st.success(f"Customer **{c['name']}** deleted.")
                                del st.session_state[confirm_key]
                                st.rerun()
                        if btn_cols[1].button("Cancel", key=f"delete_cancel_{c['id']}"):
                            del st.session_state[confirm_key]
                            st.rerun()
                    else:
                        if st.button("Delete", key=f"delete_{c['id']}", type="secondary"):
                            st.session_state[confirm_key] = True
                            st.rerun()
        else:
            st.info("No customers yet.")

    with col_form:
        st.subheader("New Customer")
        with st.form("create_customer", clear_on_submit=True):
            name = st.text_input("Name *")
            email = st.text_input("Email *")
            phone = st.text_input("Phone *")
            street = st.text_input("Street *")
            city_col, state_col, zip_col = st.columns([3, 2, 2])
            city = city_col.text_input("City *")
            state = state_col.text_input("State *")
            zip_code = zip_col.text_input("ZIP *")

            if st.form_submit_button("Create Customer", use_container_width=True):
                if not name or not email or not phone or not street or not city or not state or not zip_code:
                    st.warning("All fields are required.")
                else:
                    result = api_post("/api/customers", {
                        "name": name, "email": email, "phone": phone,
                        "address_street": street, "address_city": city,
                        "address_state": state, "address_zip": zip_code,
                    })
                    if result:
                        st.success(f"Customer **{result['name']}** created (ID: {result['id']})")
                        st.rerun()


# ── Services ──────────────────────────────────────────────────────────────────
with tab_services:
    col_list, col_form = st.columns([3, 2], gap="large")

    with col_list:
        st.subheader("All Services")
        if st.button("Refresh", key="refresh_services"):
            st.rerun()

        services = api_get("/api/services") or []
        status_icon = {"pending": "🟡", "in_progress": "🔵", "completed": "🟢"}

        if services:
            for s in services:
                icon = status_icon.get(s["status"], "")
                with st.expander(f"{icon} **{s['name']}** — {s['status']}"):
                    cols = st.columns(3)
                    cols[0].metric("Price", f"${float(s['price']):.2f}")
                    cols[1].metric("Cost", f"${float(s['cost']):.2f}")
                    cols[2].metric("Customer ID", s["customer_id"])
                    if s.get("description"):
                        st.write(s["description"])
                    if s["status"] != "completed":
                        if st.button("Mark Complete", key=f"complete_{s['id']}"):
                            result = api_post(f"/api/services/{s['id']}/complete", {})
                            if result:
                                st.success("Marked as completed.")
                                st.rerun()
        else:
            st.info("No services yet.")

    with col_form:
        st.subheader("New Service")
        customers = api_get("/api/customers") or []
        customer_options = {f"{c['name']} (ID:{c['id']})": c["id"] for c in customers}

        with st.form("create_service", clear_on_submit=True):
            if customer_options:
                selected = st.selectbox("Customer *", options=list(customer_options.keys()))
                customer_id = customer_options[selected]
            else:
                st.warning("No customers found. Create a customer first.")
                customer_id = None

            svc_name = st.text_input("Service Name *")
            description = st.text_area("Description", height=80)
            price_col, cost_col = st.columns(2)
            price = price_col.number_input("Price (charged) *", min_value=0.0, step=0.01)
            cost = cost_col.number_input("Cost (internal) *", min_value=0.0, step=0.01)
            service_date = st.date_input("Service Date")

            if st.form_submit_button("Create Service", use_container_width=True):
                if not svc_name or not customer_id:
                    st.warning("Customer and service name are required.")
                else:
                    result = api_post("/api/services", {
                        "customer_id": customer_id,
                        "name": svc_name,
                        "description": description or None,
                        "price": price,
                        "cost": cost,
                        "service_date": service_date.isoformat() if service_date else None,
                    })
                    if result:
                        st.success(f"Service **{result['name']}** created (ID: {result['id']})")
                        st.rerun()


# ── Invoices ──────────────────────────────────────────────────────────────────
with tab_invoices:
    col_list, col_form = st.columns([3, 2], gap="large")

    with col_list:
        st.subheader("All Invoices")
        if st.button("Refresh", key="refresh_invoices"):
            st.rerun()

        invoices = api_get("/api/invoices") or []
        inv_icon = {"draft": "📝", "sent": "📤", "paid": "✅"}

        if invoices:
            for i in invoices:
                icon = inv_icon.get(i["status"], "")
                with st.expander(f"{icon} **{i['invoice_number']}** — ${float(i['total_amount']):.2f}"):
                    cols = st.columns(3)
                    cols[0].write(f"**Status:** {i['status']}")
                    cols[1].write(f"**Customer ID:** {i['customer_id']}")
                    cols[2].write(f"**QB ID:** {i.get('quickbooks_invoice_id') or '—'}")
                    if i.get("notes"):
                        st.write(f"**Notes:** {i['notes']}")
                    if i["status"] != "paid":
                        if st.button("Send to QuickBooks", key=f"qb_{i['id']}"):
                            result = api_post(f"/api/invoices/{i['id']}/quickbooks", {})
                            if result:
                                st.success(f"Sent to QuickBooks: {result.get('qb_invoice_id')}")
                                st.rerun()
        else:
            st.info("No invoices yet.")

    with col_form:
        st.subheader("New Invoice")
        customers = api_get("/api/customers") or []
        customer_options = {f"{c['name']} (ID:{c['id']})": c["id"] for c in customers}

        with st.form("create_invoice", clear_on_submit=True):
            if customer_options:
                selected_customer = st.selectbox(
                    "Customer *", options=list(customer_options.keys()), key="inv_customer"
                )
                inv_customer_id = customer_options[selected_customer]

                # Load completed services for that customer
                all_services = api_get("/api/services") or []
                completed = [
                    s for s in all_services
                    if s["customer_id"] == inv_customer_id and s["status"] == "completed"
                ]
                svc_options = {f"{s['name']} — ${float(s['price']):.2f} (ID:{s['id']})": s["id"] for s in completed}

                if svc_options:
                    selected_svcs = st.multiselect(
                        "Completed Services *", options=list(svc_options.keys())
                    )
                    service_ids = [svc_options[s] for s in selected_svcs]
                else:
                    st.info("No completed services for this customer.")
                    service_ids = []
            else:
                st.warning("No customers found. Create a customer first.")
                inv_customer_id = None
                service_ids = []

            notes = st.text_area("Notes", height=68)

            if st.form_submit_button("Create Invoice", use_container_width=True):
                if not inv_customer_id or not service_ids:
                    st.warning("Select a customer and at least one completed service.")
                else:
                    payload = {"customer_id": inv_customer_id, "service_ids": service_ids}
                    if notes:
                        payload["notes"] = notes
                    result = api_post("/api/invoices", payload)
                    if result:
                        st.success(f"Invoice **{result['invoice_number']}** created — ${float(result['total_amount']):.2f}")
                        st.rerun()
