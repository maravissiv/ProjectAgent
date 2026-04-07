# Orchestrator Agent

Root agent that coordinates all sub-agents via A2A protocol. Acts as the Project Management AI assistant, delegating to Task Manager, Calendar, and Notes agents.

## Prerequisites

- Python 3.13+
- All sub-agents running and accessible:
  - Task Manager Agent (default: `http://localhost:8001`)
  - Calendar Agent (default: `http://localhost:8002`)
  - Notes Agent (default: `http://localhost:8003`)

## Environment Variables

For Vertex AI:
```bash
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=YourProjectNameHere
GOOGLE_CLOUD_LOCATION=DesiredLocationHere
PROJECT_ID=ProjectIDHere
PROJECT_NUMBER=ProjectNumberHere
SA_NAME=proj1-service
SERVICE_ACCOUNT=proj1-service@ProjectIDHere.iam.gserviceaccount.com
MODEL="gemini-2.5-flash"
TASK_AGENT_URL=https://task-manager-agent-ProjectNumberHere.Replace.run.app
CALENDAR_AGENT_URL=https://calendar-agent-ProjectNumberHere.Replace.run.app
NOTES_AGENT_URL=https://notes-agent-ProjectNumberHere.Replace.run.app
```

## Local Run

### Option A: Standalone A2A server
```bash
cd orchestrator_agent
pip install -r requirements.txt
uvicorn serve:a2a_app --host localhost --port 8000
```

### Option B: ADK Web UI (from parent directory)
```bash
cd ..
pip install -r requirements.txt
adk web
# Then select "orchestrator_agent" in the browser UI
```

### Option C: FastAPI server (from parent directory)
```bash
cd ..
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```


## Full Stack Local Startup Order

```bash
# Terminal 1: Task Manager MCP Server
cd task_manager_mcp && python server.py

# Terminal 2: Task Manager Agent
cd task_manager_agent && uvicorn serve:a2a_app --host localhost --port 8001

# Terminal 3: Calendar Agent
cd calendar_agent && uvicorn serve:a2a_app --host localhost --port 8002

# Terminal 4: Notes Agent
cd notes_agent && uvicorn serve:a2a_app --host localhost --port 8003

# Terminal 5: Orchestrator (choose one)
cd orchestrator_agent && uvicorn serve:a2a_app --host localhost --port 8000
# OR from project root:
adk web
```

## Testing

```bash
# Check agent card
curl http://localhost:8000/.well-known/agent.json
```

## Demo Scenarios

**Pattern 1 — Fan-out (parallel delegation):**
- "What's on my plate today?" → task_agent + calendar_agent + notes_agent in parallel

**Pattern 2 — Sequential chaining:**
- "Schedule a review of our high-priority tasks" → task_agent → calendar_agent (freebusy → create)

**Pattern 3 — Intelligent scheduling:**
- "Block time for overdue tasks" → task_agent (overdue) → calendar_agent (freebusy → create focus blocks)

**Pattern 4 — Cross-agent briefing prep (ReAct):**
- "Prepare me for the client meeting" → task_agent (semantic search) + calendar_agent (search) + notes_agent (search) → notes_agent (save briefing)

**Pattern 5 — Sprint retrospective:**
- "Run the sprint retrospective" → calendar_agent (2 weeks) + task_agent (summary + filter) → notes_agent (save retro)

**Pattern 6 — Daily standup automation:**
- "Generate my standup notes" → task_agent (summary + blockers) + calendar_agent (today) → notes_agent (save standup)

**Pattern 7 — End-of-day wrap-up (full 3-agent orchestration):**
- "Wrap up my day" → task_agent + calendar_agent + notes_agent (gather) → notes_agent (save EOD summary)

## Command to deploy

Ensure the agent card is updated.

```bash
cd orchestrator_agent
source .env
adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=Replace \
  --service_name=orchestrator-agent \
  --with_ui \
  --a2a \
  . \
  -- \
  --service-account=$SERVICE_ACCOUNT 
```