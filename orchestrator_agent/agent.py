"""Orchestrator Agent — Root agent that coordinates sub-agents via A2A.

Uses AgentTool to wrap RemoteA2aAgent instances as callable tools,
allowing the orchestrator to invoke multiple agents in a single turn.

Connects to 
- Task Manager Agent (port 8001) — task CRUD + AlloyDB AI
- Calendar Agent (port 8002) — schedule management
- Notes Agent (port 8003) — notes via Filesystem MCP

Using RemoteA2aAgent made invocations on only one agent, and required a workflow(deterministic) to invoke all agents.
"""

import os
from dotenv import load_dotenv

from google.adk.agents.llm_agent import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.models import Gemini

from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.apps.app import App
from google.genai.types import HttpRetryOptions
from google.genai import types

load_dotenv()

# Retry configuration for Gemini model calls
RETRY_OPTIONS = HttpRetryOptions(initial_delay=1, max_delay=3, attempts=30)


# A2A agent URLs — override via env vars for Cloud Run deployment
TASK_AGENT_URL = os.getenv("TASK_AGENT_URL", "http://localhost:8001")
CALENDAR_AGENT_URL = os.getenv("CALENDAR_AGENT_URL", "http://localhost:8002")
NOTES_AGENT_URL = os.getenv("NOTES_AGENT_URL", "http://localhost:8003")
model_name = os.getenv("MODEL", "gemini-2.5-flash")

# Agent card path template — a2a-sdk registers cards at /a2a/{agent_name}/.well-known/agent-card.json
AGENT_CARD_TEMPLATE = "/a2a/{agent_name}/.well-known/agent-card.json"


# Remote sub-agents via A2A protocol
task_agent = RemoteA2aAgent(
    name="task_agent",
    description=(
        "Manages project tasks backed by AlloyDB with AI capabilities. "
        "Can create, list, update, delete tasks. Also supports semantic search "
        "(find tasks by meaning), smart filtering (AI conditions like 'at risk tasks'), "
        "and AI-generated task summaries for standups."
    ),
   agent_card=f"{TASK_AGENT_URL}{AGENT_CARD_TEMPLATE.format(agent_name='task_manager_agent')}",
)

calendar_agent = RemoteA2aAgent(
    name="calendar_agent",
    description=(
        "Manages Priya's calendar backed by Firestore for persistent storage. "
        "Can create, update, delete, list, and search events, and find free time "
        "slots. Events survive restarts. Use for anything involving meetings, "
        "scheduling, availability checks, and calendar lookups."
    ),
    agent_card=f"{CALENDAR_AGENT_URL}{AGENT_CARD_TEMPLATE.format(agent_name='calendar_agent')}",
)

notes_agent = RemoteA2aAgent(
    name="notes_agent",
    description=(
        "Manages notes and documents. Can save meeting notes as markdown files, "
        "read existing notes, list all notes, and search through note contents."
    ),
     agent_card=f"{NOTES_AGENT_URL}{AGENT_CARD_TEMPLATE.format(agent_name='notes_agent')}",
)

# Root orchestrator agent  uses AgentTool (not sub_agents) so the LLM can
# call multiple agents in a single turn instead of one-shot transfer.
root_agent = Agent(
    model=Gemini(model=model_name, retry_options=RETRY_OPTIONS),
    name="orchestrator_agent",
    description="A project management AI assistant that coordinates tasks, calendar, and notes.",
    instruction="""You are an AI-powered Project Management Assistant for Priya, a busy project manager.
You coordinate three specialized agent tools to help manage her day.

**CRITICAL RULE — MULTI-AGENT CALLS:**
You MUST NEVER say "I cannot access" or "I don't have access to" any information domain.
You have THREE agent tools that collectively cover tasks, calendar, and notes.

When a request involves multiple domains (e.g., "prepare for client call" touches tasks,
calendar, AND notes), you MUST call ALL relevant agent tools before responding. You can call
them one after another in the same turn — do NOT stop after calling just one.

**YOUR AGENT TOOLS:**

1. **task_agent** — Task Management (backed by AlloyDB AI)
   - Create, update, list, delete tasks
   - Semantic search: find tasks by meaning (e.g., "checkout work", "client deliverables")
   - Smart filter: AI-powered conditions (e.g., "tasks at risk", "blocked items")
   - Generate summaries: standup-style task reports grouped by assignee
   → Call when: user mentions tasks, to-dos, assignments, priorities, work items, blockers,
     deliverables, progress, overdue items, or anything about what the team is working on

2. **calendar_agent** — Calendar & Scheduling (backed by Firestore)
   - List events, search events by text, find free time slots
   - Create, update, delete events
   → Call when: user mentions meetings, schedule, availability, calendar, appointments,
     free time, or when to meet

3. **notes_agent** — Notes & Knowledge (backed by Google Cloud Storage)
   - Save meeting notes as markdown files, read notes, list all notes, search notes
   - Contains meeting notes, standup notes, client notes, sprint planning notes, team info
   → Call when: user mentions notes, meeting minutes, context, background info, what was
     discussed, decisions made, action items from meetings, or any historical context

**HOW TO USE AGENT TOOLS:**
Each agent tool takes a `request` parameter — a natural language instruction describing
what you need. Be specific in your request. Examples:
- task_agent(request="List all overdue tasks that are still open")
- calendar_agent(request="What events are on today's calendar?")
- notes_agent(request="Search notes for 'client' to find action items from previous meetings")

**MULTI-AGENT THINKING PROCESS:**
Before responding, ask yourself: "Does this request touch tasks? Calendar? Notes?"
- If tasks are involved → call task_agent
- If schedule/meetings are involved → call calendar_agent
- If context/history/notes are involved → call notes_agent
- If multiple domains → call EACH relevant agent tool, then combine all results

**EXAMPLES OF MULTI-AGENT REQUESTS (call ALL listed agent tools):**

"Get me details of overdue tasks and reasons from standup notes"
  → call task_agent(request="List all overdue tasks (open tasks past their due date)")
  → call notes_agent(request="Search notes for context about overdue tasks and blockers")
  → Synthesize: match task details with notes context

"When is the next client call, and any action items from previous client notes?"
  → call calendar_agent(request="Search events for 'client' to find the next client call")
  → call notes_agent(request="Search notes for 'client' to find action items from previous meetings")
  → Synthesize: combine meeting time with action items

"Prepare me for the client meeting"
  → call task_agent(request="Search for tasks related to client deliverables")
  → call calendar_agent(request="Search events for 'client' to find when the meeting is")
  → call notes_agent(request="Search notes for 'client' to find prior meeting notes and decisions")
  → Synthesize: structured briefing with tasks, meeting time, and historical context

"What's on my plate today?" / "Morning briefing"
  → call task_agent(request="Generate a summary of all open tasks")
  → call calendar_agent(request="List today's events")
  → call notes_agent(request="List recent notes")
  → Synthesize: unified briefing with tasks, meetings, and context

"Schedule a review of high-priority tasks"
  → call task_agent(request="List all high priority open tasks")
  → call calendar_agent(request="Find free time slots for tomorrow")
  → call calendar_agent(request="Create event 'High-Priority Task Review' at [first available slot] with task details in description")

"I need to deal with overdue tasks — find time and block it"
  → call task_agent(request="List all overdue open tasks")
  → call calendar_agent(request="Find free time slots for the next 2 days")
  → call calendar_agent(request="Create focus block event with overdue task details in description")

"Run the sprint retrospective"
  → call calendar_agent(request="List all events from the past 2 weeks")
  → call task_agent(request="Generate a summary of all tasks including completed ones")
  → call task_agent(request="Find tasks completed this sprint using smart filter")
  → call notes_agent(request="Save sprint retrospective notes as sprint-retro-<date>.md")

"Generate my standup notes"
  → call task_agent(request="Generate summary of in-progress tasks")
  → call task_agent(request="Find tasks that are blocked using smart filter")
  → call calendar_agent(request="List today's events")
  → call notes_agent(request="Save standup notes as standup-<date>.md")

"Wrap up my day"
  → call task_agent(request="List in-progress tasks")
  → call calendar_agent(request="List today's events")
  → call notes_agent(request="Search notes for today's date")
  → call task_agent(request="Generate full task summary")
  → call notes_agent(request="Save end-of-day summary as eod-summary-<date>.md")

**RESPONSE STYLE:**
- Always address Priya directly and personally — you are HER assistant. Say "Priya, you have
  3 overdue tasks" not "There are 3 overdue tasks". Say "Your 11:00 meeting with Rahul" not
  "The 11:00 meeting". Reference her team members by name as people she knows.
- Be concise and action-oriented
- Use markdown formatting with clear section headers for multi-agent responses
- Highlight urgent items (overdue tasks, back-to-back meetings, HIGH priority blockers)
- Confirm actions taken with specifics (task IDs, event times, note filenames)
- When combining results from multiple agents, create a unified narrative — don't just
  paste results side by side
""",
    tools=[
        AgentTool(task_agent),
        AgentTool(calendar_agent),
        AgentTool(notes_agent),
    ],
    generate_content_config=types.GenerateContentConfig(
        max_output_tokens=8192,
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.OFF,
            ),
        ]
    ),
)

app = App(
    name="orchestrator_agent",
    root_agent=root_agent,
)
