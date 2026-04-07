"""Task Manager MCP Server — Streamable HTTP transport.

A custom-built MCP server backed by AlloyDB with AI capabilities.
Exposes 7 tools: CRUD (create, list, update, delete) + AlloyDB AI
(semantic_search, smart_filter, generate_summary).

Run:
  python task_manager_mcp/server.py

Serves on http://localhost:8010/mcp
"""

import contextlib
import json
import logging
import os
import sys
from collections.abc import AsyncIterator
from typing import Any

from dotenv import load_dotenv

load_dotenv()

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send

# Add parent directory to path so we can import db module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import (
    create_task, list_tasks, update_task, delete_task,
    semantic_search_tasks, smart_filter_tasks, generate_task_summary,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP Server definition
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    types.Tool(
        name="create_task",
        description="Create a new task with a title, description, assignee, priority, due date, and tags. The task is stored in AlloyDB and automatically gets a vector embedding for semantic search.",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title (required)"},
                "description": {"type": "string", "description": "Detailed task description"},
                "assignee": {"type": "string", "description": "Person assigned to the task"},
                "priority": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"], "description": "Task priority (default: MEDIUM)"},
                "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format"},
                "tags": {"type": "string", "description": "Comma-separated tags (e.g., 'frontend,bugfix,checkout')"},
            },
            "required": ["title"],
        },
    ),
    types.Tool(
        name="list_tasks",
        description="List tasks with optional filters for status, priority, assignee, and due date. Returns tasks ordered by priority (HIGH first) then by due date.",
        inputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["open", "in_progress", "done"], "description": "Filter by task status"},
                "priority": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"], "description": "Filter by priority"},
                "assignee": {"type": "string", "description": "Filter by assignee name"},
                "due_before": {"type": "string", "description": "Filter tasks due on or before this date (YYYY-MM-DD)"},
            },
        },
    ),
    types.Tool(
        name="update_task",
        description="Update an existing task's fields (title, description, status, priority, due_date, assignee). Only provide the fields you want to change. The vector embedding is automatically regenerated if the title or description changes.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "ID of the task to update (required)"},
                "title": {"type": "string", "description": "New title"},
                "description": {"type": "string", "description": "New description"},
                "status": {"type": "string", "enum": ["open", "in_progress", "done"], "description": "New status"},
                "priority": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"], "description": "New priority"},
                "due_date": {"type": "string", "description": "New due date (YYYY-MM-DD)"},
                "assignee": {"type": "string", "description": "New assignee"},
            },
            "required": ["task_id"],
        },
    ),
    types.Tool(
        name="delete_task",
        description="Delete a task by its ID. This is permanent.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "ID of the task to delete"},
            },
            "required": ["task_id"],
        },
    ),
    types.Tool(
        name="semantic_search_tasks",
        description="Search tasks using natural language semantic similarity. Uses AlloyDB's vector embeddings (text-embedding-005) and pgvector cosine distance to find tasks related to a query even if the exact words don't match. Example: 'frontend checkout work' will find tasks about the checkout UI rewrite.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "top_k": {"type": "integer", "description": "Number of results to return (default: 5, max: 20)"},
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="smart_filter_tasks",
        description="Filter tasks using a natural language condition powered by AlloyDB AI's ai.if() function. The AI evaluates each task against the condition and returns only matching ones. Examples: 'this task is at risk of missing its deadline', 'this is a frontend-related task', 'this task seems blocked or needs help'.",
        inputSchema={
            "type": "object",
            "properties": {
                "condition": {"type": "string", "description": "Natural language condition to evaluate against each task"},
            },
            "required": ["condition"],
        },
    ),
    types.Tool(
        name="generate_task_summary",
        description="Generate a natural language summary of tasks using AlloyDB AI's ai.generate() function. The AI produces a standup-style summary grouped by assignee with urgency highlights. Scope can be: 'all open', 'high priority', 'in progress', 'all', etc.",
        inputSchema={
            "type": "object",
            "properties": {
                "scope": {"type": "string", "description": "Scope of tasks to summarize (e.g., 'all open', 'high priority', 'in progress'). Default: 'all open'"},
            },
        },
    ),
]

# Map tool names to handler functions
TOOL_HANDLERS = {
    "create_task": create_task,
    "list_tasks": list_tasks,
    "update_task": update_task,
    "delete_task": delete_task,
    "semantic_search_tasks": semantic_search_tasks,
    "smart_filter_tasks": smart_filter_tasks,
    "generate_task_summary": generate_task_summary,
}


def create_mcp_server() -> Server:
    """Create and configure the MCP server."""
    app = Server("task-manager-mcp-server")

    @app.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        logger.info("MCP: list_tools requested")
        return TOOL_DEFINITIONS

    @app.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        logger.info(f"MCP: call_tool '{name}' with args: {arguments}")

        handler = TOOL_HANDLERS.get(name)
        if not handler:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        try:
             # Run synchronous pg8000 DB calls in a thread so they don't block
            # the async event loop (critical for AlloyDB AI functions like
            # embedding(), ai.if(), ai.generate() which make Vertex AI calls
            # and can take several seconds).
            result = await anyio.to_thread.run_sync(lambda: handler(**arguments))
            return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        except Exception as e:
            logger.error(f"MCP: Error in tool '{name}': {e}")
            return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]

    return app


# ---------------------------------------------------------------------------
# Streamable HTTP Server
# ---------------------------------------------------------------------------

def main(port: int = 8010):
    """Run the MCP server with Streamable HTTP transport."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    mcp_app = create_mcp_server()

    session_manager = StreamableHTTPSessionManager(
        app=mcp_app,
        event_store=None,
        json_response=True,
        stateless=True,
    )

    async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            logger.info(f"Task Manager MCP Server started on http://localhost:{port}/")
            logger.info("Tools: create_task, list_tasks, update_task, delete_task, semantic_search_tasks, smart_filter_tasks, generate_task_summary")
            try:
                yield
            finally:
                logger.info("Task Manager MCP Server shutting down...")

    starlette_app = Starlette(
        debug=False,
        routes=[
            Mount("/", app=handle_streamable_http),
        ],
        lifespan=lifespan,
    )

    import uvicorn
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    port = int(os.getenv("MCP_SERVER_PORT", "8010"))
    main(port=port)
