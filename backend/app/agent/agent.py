"""
Claude agent with tool-use loop.

Exposes POST /api/agent/chat which the Streamlit UI calls.
Session history is kept in-memory (swap for Redis via SESSION_BACKEND env var).
"""
import json
import logging
import os
from typing import Any

import anthropic
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.agent import ChatRequest, ChatResponse
from app.agent.tools import TOOL_DEFINITIONS, TOOL_HANDLERS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

SYSTEM_PROMPT = """You are a helpful business assistant for a multiservice company.
You help manage customers, track services performed, and handle invoicing.

You have access to tools to:
- Create, list, and update customers
- Create and track services (with cost to the company and price charged to customers)
- Mark services as completed
- Create invoices from completed services
- Send invoices to QuickBooks

Always confirm key details before creating records. When listing results, present them clearly.
When creating an invoice, first verify the services are completed or ask the user to confirm."""

_client = anthropic.AsyncAnthropic()

# In-memory session store: {session_id: [message_dicts]}
# Swap: if SESSION_BACKEND=redis, use aioredis instead
_sessions: dict[str, list[dict]] = {}


async def _execute_tool(tool_name: str, tool_input: dict, db: AsyncSession) -> Any:
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return f"Unknown tool: {tool_name}"
    try:
        return await handler(db=db, **tool_input)
    except Exception as exc:
        logger.exception("Tool %s failed", tool_name)
        return f"Error executing {tool_name}: {str(exc)}"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    session_id = request.session_id
    history = _sessions.setdefault(session_id, [])
    history.append({"role": "user", "content": request.message})

    # Tool-use loop
    while True:
        response = await _client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=history,
        )

        # Append assistant response to history
        history.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract text response
            text = next(
                (block.text for block in response.content if hasattr(block, "text")),
                "Done.",
            )
            return ChatResponse(response=text, session_id=session_id)

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await _execute_tool(block.name, block.input, db)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })

            history.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason
        break

    return ChatResponse(response="An unexpected error occurred.", session_id=session_id)


@router.delete("/chat/{session_id}", status_code=204)
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    _sessions.pop(session_id, None)
