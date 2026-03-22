from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.api import customers, services, invoices, auth
from app.agent.agent import router as agent_router
from app.mcp_server.server import create_mcp_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Ab001 - Multiservice Management", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API
app.include_router(customers.router, prefix="/api")
app.include_router(services.router, prefix="/api")
app.include_router(invoices.router, prefix="/api")
app.include_router(auth.router, prefix="/api")

# Claude agent endpoint
app.include_router(agent_router, prefix="/api")

# MCP HTTP server (SSE) — accessible at /mcp/sse
mcp_app = create_mcp_app()
app.mount("/mcp", mcp_app)


@app.get("/health")
async def health():
    return {"status": "ok"}
