# Ab001 — Pending Tasks

## Test Coverage Gaps (current overall: 87% ✅)

- [x] **Add Claude provider test for `agent.py`**
- [x] **Add MCP server tests** — `tests/integration/test_mcp_server.py`
- [x] **Exclude `RealQuickBooksClient` from coverage** — `# pragma: no cover` added
- [x] **Fill API 404/409 branch gaps** — added to customers, services, invoices test files

## QuickBooks Integration

- [x] **Prevent duplicate invoices being sent to QuickBooks**
  - `invoices.py` returns 409 if `quickbooks_invoice_id` already set
  - `tools.py` returns "already sent" message to the agent

## Agent Behavior

- [x] **Required-field validation layer in `_execute_tool`**
  - `_TOOL_REQUIRED` dict built at module level from `TOOL_DEFINITIONS`
  - Missing fields returned as error string — agent is forced to ask the user

- [ ] **Further agent refinement: service cost/price hallucination**
  - The validation layer blocks structurally missing fields, but the agent may still
    carry over or invent numeric values (cost, price) from earlier conversation context.
  - Consider adding a stronger system prompt rule specifically for `create_service`
    cost and price fields.
  - File: `backend/app/agent/agent.py` (SYSTEM_PROMPT)

## Invoice Workflow

- [ ] **Gate invoice submission on completed services**
  - Do not allow sending an invoice to QuickBooks until all linked services are marked `completed`.
  - Enforcement points: frontend button state + agent system prompt rule (already partially in place).
  - Files: `frontend/pages/1_Data_Manager.py`, `backend/app/agent/agent.py` (SYSTEM_PROMPT rule #5)

- [ ] **QuickBooks confirmation popup after service completion**
  - When a service is marked as `completed`, show a confirmation dialog:
    "All services are completed — would you like to send the invoice to QuickBooks now?"
  - If the user confirms → call `send_invoice_to_quickbooks` immediately.
  - If the user declines → do nothing; the invoice remains and can be sent manually
    via the Data Manager page.
  - Files: `frontend/pages/1_Data_Manager.py` (Streamlit `st.dialog` or `st.warning` + buttons)

## Housekeeping

- [x] **Add `pytest-cov` to `requirements-test.txt`** — pinned at 6.0.0
- [x] **Set a minimum coverage threshold** — `--cov-fail-under=85` in `pytest.ini`
  - [ ] Consider a GitHub Actions workflow that runs `pytest --cov` on every push/PR
