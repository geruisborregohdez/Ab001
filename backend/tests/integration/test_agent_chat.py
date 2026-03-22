import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import app.agent.agent as agent_module


@pytest_asyncio.fixture(autouse=True)
async def clear_sessions():
    """Wipe session state before every test."""
    agent_module._sessions.clear()
    yield
    agent_module._sessions.clear()


def _make_groq_response(text: str):
    """Build a minimal mock Groq completion response with no tool calls."""
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None

    choice = MagicMock()
    choice.message = msg

    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture
def mock_groq_client():
    """Patch groq.AsyncGroq so no real API call is made."""
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_make_groq_response("Hello! How can I help you?")
    )
    return mock_client


async def test_chat_returns_200_with_response(client, mock_groq_client):
    with patch("groq.AsyncGroq", return_value=mock_groq_client):
        resp = await client.post("/api/agent/chat", json={
            "message": "hello",
            "session_id": "test-1",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert data["response"] == "Hello! How can I help you?"
    assert data["session_id"] == "test-1"


async def test_chat_session_persists(client, mock_groq_client):
    with patch("groq.AsyncGroq", return_value=mock_groq_client):
        await client.post("/api/agent/chat", json={
            "message": "first message",
            "session_id": "persist-test",
        })
        await client.post("/api/agent/chat", json={
            "message": "second message",
            "session_id": "persist-test",
        })

    # Session should exist and have 4 entries (2 user + 2 assistant)
    assert "persist-test" in agent_module._sessions
    history = agent_module._sessions["persist-test"]
    user_msgs = [m for m in history if m["role"] == "user"]
    assert len(user_msgs) == 2


async def test_chat_different_sessions_are_isolated(client, mock_groq_client):
    with patch("groq.AsyncGroq", return_value=mock_groq_client):
        await client.post("/api/agent/chat", json={
            "message": "session A message",
            "session_id": "session-a",
        })
        await client.post("/api/agent/chat", json={
            "message": "session B message",
            "session_id": "session-b",
        })

    assert "session-a" in agent_module._sessions
    assert "session-b" in agent_module._sessions
    assert agent_module._sessions["session-a"] != agent_module._sessions["session-b"]


async def test_clear_session_returns_204(client):
    agent_module._sessions["to-clear"] = [{"role": "user", "content": "hi"}]
    resp = await client.delete("/api/agent/chat/to-clear")
    assert resp.status_code == 204
    assert "to-clear" not in agent_module._sessions


async def test_clear_nonexistent_session_returns_204(client):
    resp = await client.delete("/api/agent/chat/does-not-exist")
    assert resp.status_code == 204


async def test_chat_uses_groq_import_in_agent(client, mock_groq_client):
    """Verify the groq client is actually called (not Claude) with default provider."""
    with patch("groq.AsyncGroq", return_value=mock_groq_client) as mock_cls:
        await client.post("/api/agent/chat", json={
            "message": "test",
            "session_id": "groq-test",
        })
    mock_cls.assert_called_once()
    mock_groq_client.chat.completions.create.assert_called_once()


async def test_chat_claude_provider_returns_200(client, monkeypatch):
    """Claude provider path returns 200 with the mocked text response."""
    monkeypatch.setattr(agent_module, "AGENT_PROVIDER", "claude")

    text_block = MagicMock()
    text_block.text = "Hello from Claude!"
    text_block.type = "text"

    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [text_block]

    mock_claude = MagicMock()
    mock_claude.messages.create = AsyncMock(return_value=mock_response)

    with patch("anthropic.AsyncAnthropic", return_value=mock_claude):
        resp = await client.post("/api/agent/chat", json={
            "message": "hi",
            "session_id": "claude-test",
        })

    assert resp.status_code == 200
    assert resp.json()["response"] == "Hello from Claude!"
