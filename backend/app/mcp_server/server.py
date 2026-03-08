"""
MCP HTTP server (SSE transport) mounted at /mcp.

Exposes the same tool functions as the Claude agent, so any MCP-compatible client
(Claude Desktop, Python scripts, other LLMs) can connect and call tools directly.

Usage:
  - Local: http://localhost:8000/mcp/sse
  - Cloud: http://<your-ec2-ip>/mcp/sse (proxied through Nginx)

Claude Desktop config example:
  {
    "mcpServers": {
      "ab001": {
        "url": "http://localhost:8000/mcp/sse"
      }
    }
  }
"""
import json
import logging

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount

from app.db.database import AsyncSessionLocal
from app.agent.tools import TOOL_DEFINITIONS, TOOL_HANDLERS

logger = logging.getLogger(__name__)

mcp_server = Server("ab001")


def _definitions_to_mcp_tools() -> list[Tool]:
    tools = []
    for defn in TOOL_DEFINITIONS:
        tools.append(Tool(
            name=defn["name"],
            description=defn["description"],
            inputSchema=defn["input_schema"],
        ))
    return tools


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    return _definitions_to_mcp_tools()


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    try:
        async with AsyncSessionLocal() as db:
            result = await handler(db=db, **arguments)
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as exc:
        logger.exception("MCP tool %s failed", name)
        return [TextContent(type="text", text=f"Error: {str(exc)}")]


def create_mcp_app() -> Starlette:
    """Returns a Starlette app that can be mounted at /mcp in FastAPI."""
    sse = SseServerTransport("/mcp/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await mcp_server.run(streams[0], streams[1], mcp_server.create_initialization_options())

    async def handle_messages(request):
        await sse.handle_post_message(request.scope, request.receive, request._send)

    return Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=handle_messages),
        ]
    )
