"""
Tests for the MCP server tool dispatch layer.

Calls the `call_tool` handler directly (no SSE/HTTP) by patching
AsyncSessionLocal to use the test database session.
"""
import json
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest

from app.mcp_server.server import call_tool


def _text(results) -> str:
    """Extract text content from MCP call_tool result list."""
    return results[0].text


@pytest.fixture
def patch_db(db_session):
    """Patch AsyncSessionLocal so the MCP server uses the test DB session."""
    @asynccontextmanager
    async def _mock_session():
        yield db_session

    return patch("app.mcp_server.server.AsyncSessionLocal", _mock_session)


async def test_list_tools_returns_all_tool_names():
    from app.mcp_server.server import list_tools
    from app.agent.tools import TOOL_DEFINITIONS

    tools = await list_tools()
    defined_names = {t["name"] for t in TOOL_DEFINITIONS}
    returned_names = {t.name for t in tools}
    assert defined_names == returned_names


async def test_call_tool_unknown_returns_error(patch_db):
    with patch_db:
        results = await call_tool("does_not_exist", {})
    assert "Unknown tool" in _text(results)


async def test_call_tool_create_customer(patch_db):
    with patch_db:
        results = await call_tool("create_customer", {
            "name": "MCP Corp",
            "email": "mcp@example.com",
            "phone": "555-2000",
            "address_street": "10 MCP Blvd",
            "address_city": "Austin",
            "address_state": "TX",
            "address_zip": "78701",
        })
    data = json.loads(_text(results))
    assert data["name"] == "MCP Corp"
    assert data["email"] == "mcp@example.com"
    assert "id" in data


async def test_call_tool_list_customers(patch_db):
    with patch_db:
        # Create a customer first
        await call_tool("create_customer", {
            "name": "Listed Co",
            "email": "listed@example.com",
            "phone": "555-3000",
            "address_street": "1 List St",
            "address_city": "Denver",
            "address_state": "CO",
            "address_zip": "80201",
        })
        results = await call_tool("list_customers", {})

    customers = json.loads(_text(results))
    assert isinstance(customers, list)
    assert any(c["name"] == "Listed Co" for c in customers)


async def test_call_tool_missing_required_fields_returns_error(patch_db):
    """The agent validation layer should block calls with missing required fields."""
    with patch_db:
        results = await call_tool("create_customer", {"name": "Incomplete"})
    text = _text(results)
    # MCP server doesn't use _execute_tool from agent, so this hits handler directly.
    # Expect a Python TypeError or validation error from the tool function.
    assert "error" in text.lower() or "missing" in text.lower() or "required" in text.lower()
