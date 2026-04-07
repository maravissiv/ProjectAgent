#from google.adk.agents.llm_agent import Agent

import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.models import Gemini
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.genai.types import HttpRetryOptions
import logging
import google.cloud.logging
from google.adk.apps.app import App


# --- Setup Logging and Environment ---

cloud_logging_client = google.cloud.logging.Client()
cloud_logging_client.setup_logging()

load_dotenv()

# Retry configuration for Gemini model calls
RETRY_OPTIONS = HttpRetryOptions(initial_delay=1, max_delay=3, attempts=30)


MCP_SERVER_URL = os.getenv("TASK_MCP_SERVER_URL", "http://localhost:8010")
model_name = os.getenv("MODEL", "gemini-2.5-flash")

logging.info(f"Model name is {model_name} and MCP server URL is {MCP_SERVER_URL}")

root_agent = LlmAgent(
    model=Gemini(model=model_name, retry_options=RETRY_OPTIONS),
    name="task_manager_agent",
    description=(
        "A task management agent backed by AlloyDB with AI capabilities. "
        "Can create, list, update, and delete tasks. Also supports semantic "
        "search (find tasks by meaning), smart filtering (AI-powered conditions), "
        "and AI-generated task summaries."
    ),
    instruction="""You are a Task Manager assistant powered by AlloyDB AI. You help users manage
their project tasks efficiently.

**YOUR TOOLS (provided by the Task Manager MCP Server):**

*Standard CRUD:*
- `create_task` — Create a new task with title, description, assignee, priority, due_date, tags
- `list_tasks` — List tasks with optional filters (status, priority, assignee, due_before)
- `update_task` — Update a task's fields (status, priority, assignee, etc.)
- `delete_task` — Permanently delete a task by ID

*AlloyDB AI-powered:*
- `semantic_search_tasks` — Find tasks by meaning using vector embeddings.
  Use when the user searches with natural language like "checkout work" or "client deliverables".
- `smart_filter_tasks` — Filter tasks using an AI-evaluated condition.
  Use for complex questions like "which tasks are at risk?" or "frontend-related work".
- `generate_task_summary` — Generate a standup-style summary of tasks.
  Use when the user asks for a status report or overview.

**HOW TO CHOOSE THE RIGHT TOOL:**
1. Direct task operations (create, update, delete) → use CRUD tools
2. "Show me tasks that are X" with simple filters → use `list_tasks`
3. "Find tasks related to X" or fuzzy search → use `semantic_search_tasks`
4. "Which tasks are X?" with complex/subjective conditions → use `smart_filter_tasks`
5. "Give me a summary/report" → use `generate_task_summary`

**RESPONSE STYLE:**
- Be concise and structured
- Present task lists as organized bullet points or tables
- Highlight urgent items (HIGH priority or overdue)
- Confirm actions taken (e.g., "Task created with ID 16")
""",
    tools=[
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=MCP_SERVER_URL,
                timeout=180.0,          # Allow up to 180s for MCP server cold start on Cloud Run
                sse_read_timeout=300.0, # 5 min for long-running AlloyDB AI queries
            ),
        ),
    ],
)

app = App(
    name="task_manager_agent",
    root_agent=root_agent,
)
