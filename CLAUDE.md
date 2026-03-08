# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Ab001 is a Python POC application for a multiservice company to manage customers, services, and invoices, with a Claude AI agent exposed both via a Streamlit web UI and an MCP HTTP server (for programmatic access).

## Local development

```bash
# Prerequisites: Docker + Docker Compose

cp .env.example .env          # add ANTHROPIC_API_KEY
docker compose up --build     # starts backend (8000), frontend (8501), nginx (80)
```

App is at `http://localhost`. Backend API at `http://localhost/api`. MCP SSE endpoint at `http://localhost/mcp/sse`.

To run backend only (without Docker):
```bash
cd backend
pip install -r requirements.txt
mkdir -p data
uvicorn app.main:app --reload --port 8000
```

## Architecture

```
backend/app/
├── db/           → SQLAlchemy models + repositories (Customer, Service, Invoice, InvoiceLineItem)
├── schemas/      → Pydantic schemas (Create/Update/Read per entity)
├── api/          → FastAPI REST routers (mounted at /api)
├── agent/
│   ├── tools.py  → Shared tool functions + TOOL_DEFINITIONS + TOOL_HANDLERS registry
│   └── agent.py  → Claude tool-use loop, POST /api/agent/chat
├── mcp_server/
│   └── server.py → MCP HTTP server (SSE), mounted at /mcp — uses same tools.py
├── integrations/
│   └── quickbooks.py → QuickBooksClient ABC + StubQuickBooksClient
└── main.py       → FastAPI app wiring everything together
```

`tools.py` is the single source of truth: both the Claude agent and the MCP server call the same async tool functions.

## Key conventions

- **Database**: SQLAlchemy async + `AsyncSession`. All DB access goes through repositories in `db/repositories/`. To swap to PostgreSQL: change `DATABASE_URL` env var — no code changes needed.
- **Tool functions**: Each tool in `tools.py` receives `db: AsyncSession` as first arg, then keyword args from Claude. Register new tools in both `TOOL_DEFINITIONS` (schema for Claude) and `TOOL_HANDLERS` (name → callable).
- **QuickBooks**: `QB_MODE=stub` uses `StubQuickBooksClient`. To implement real integration: subclass `QuickBooksClient`, add it to `get_quickbooks_client()`.
- **Agent model**: Controlled by `CLAUDE_MODEL` env var (default `claude-sonnet-4-6`).
- **Sessions**: In-memory dict in `agent.py` (`_sessions`). For Redis: swap the dict with `aioredis`.

## Swappable components

| Component | POC default | How to swap |
|---|---|---|
| Database | SQLite (file) | Change `DATABASE_URL` to `postgresql+asyncpg://...` |
| QuickBooks | Stub | Set `QB_MODE=real`, implement `RealQuickBooksClient` |
| Session store | In-memory dict | Replace `_sessions` in `agent.py` with Redis |
| Compute | EC2 t3.micro | Update Terraform to ECS Fargate |
| Model | claude-sonnet-4-6 | Set `CLAUDE_MODEL` env var |

## Connecting external MCP clients

Any MCP-compatible client can connect to the MCP SSE endpoint:

**Claude Desktop** — add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "ab001": { "url": "http://localhost/mcp/sse" }
  }
}
```

**Python client** — see `examples/mcp_client_example.py`

## Cloud deployment (AWS)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # fill in key_pair_name and anthropic_api_key
terraform init
terraform plan
terraform apply
```

Outputs: `public_ip`, `app_url`, `mcp_sse_url`, `ssh_command`.

Before deploying, update the `git clone` URL in `terraform/user_data.sh` to point to your repository.

## Adding a new tool

1. Add the async function to `backend/app/agent/tools.py`
2. Add its JSON schema to `TOOL_DEFINITIONS`
3. Register it in `TOOL_HANDLERS`
4. The tool is automatically available to both the Claude agent and the MCP server
