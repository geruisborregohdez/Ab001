"""
Multi-provider agent with tool-use loop.

Supports Groq (default) and Claude via AGENT_PROVIDER env var.
Exposes POST /api/agent/chat which the Streamlit UI calls.
Session history is kept in-memory (swap for Redis via SESSION_BACKEND env var).
"""
import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.agent import ChatRequest, ChatResponse
from app.agent.tools import TOOL_DEFINITIONS, TOOL_HANDLERS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

AGENT_PROVIDER = os.getenv("AGENT_PROVIDER", "groq")   # groq | claude
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

SYSTEM_PROMPT = """You are a helpful business assistant for a multiservice company.
You help manage customers, track services performed, and handle invoicing.

You have access to tools to:
- Create, list, and update customers
- Create and track services (with cost to the company and price charged to customers)
- Mark services as completed
- Create invoices from completed services
- Send invoices to QuickBooks

STRICT RULES — never break these:
1. NEVER invent, guess, or assume any field value (name, email, phone, address, cost, price, etc.).
   If the user has not explicitly provided a value, you MUST ask for it before calling any tool.
2. All required fields for create_customer are: name, email, phone, address_street, address_city,
   address_state, address_zip. Ask for every missing field in a single message before proceeding.
3. When listing results, present them clearly.
4. When creating an invoice, first verify the services are completed or ask the user to confirm."""

# In-memory session store: {session_id: [message_dicts]}
# Swap: if SESSION_BACKEND=redis, use aioredis instead
_sessions: dict[str, list[dict]] = {}


def _to_openai_tools(anthropic_tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool schema format to OpenAI/Groq format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t["input_schema"],
            },
        }
        for t in anthropic_tools
    ]


async def _execute_tool(tool_name: str, tool_input: dict, db: AsyncSession) -> Any:
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return f"Unknown tool: {tool_name}"
    try:
        return await handler(db=db, **tool_input)
    except Exception as exc:
        logger.exception("Tool %s failed", tool_name)
        return f"Error executing {tool_name}: {str(exc)}"


async def _chat_groq(history: list[dict], db: AsyncSession) -> tuple[str, list[dict]]:
    from groq import AsyncGroq
    client = AsyncGroq()
    tools = _to_openai_tools(TOOL_DEFINITIONS)
    working = list(history)

    while True:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + working
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        assistant_msg: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        working.append(assistant_msg)

        if msg.tool_calls:
            for tc in msg.tool_calls:
                result = await _execute_tool(
                    tc.function.name, json.loads(tc.function.arguments), db
                )
                working.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })
        else:
            return msg.content or "Done.", working


async def _chat_claude(history: list[dict], db: AsyncSession) -> tuple[str, list[dict]]:
    import anthropic
    client = anthropic.AsyncAnthropic()

    while True:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=history,
        )
        history.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text = next(
                (block.text for block in response.content if hasattr(block, "text")),
                "Done.",
            )
            return text, history

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

        break

    return "An unexpected error occurred.", history


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    session_id = request.session_id
    history = _sessions.setdefault(session_id, [])
    history.append({"role": "user", "content": request.message})

    if AGENT_PROVIDER == "claude":
        text, history = await _chat_claude(history, db)
    else:
        text, history = await _chat_groq(history, db)

    _sessions[session_id] = history
    return ChatResponse(response=text, session_id=session_id)


@router.delete("/chat/{session_id}", status_code=204)
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    _sessions.pop(session_id, None)
