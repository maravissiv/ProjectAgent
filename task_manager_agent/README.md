# Task Manager Agent

ADK agent that connects to the Task Manager MCP Server (Streamable HTTP) to provide task management with AlloyDB AI capabilities. Exposed via A2A protocol on port 8001.

## Prerequisites

- Python 3.13+
- Task Manager MCP Server running (see `task_manager_mcp/`)

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
TASK_MCP_SERVER_URL="https://taskmanager-mcp-ProjectNumberHere.Replace.run.app"
```

## Local Run

```bash
cd task_manager_agent
pip install -r requirements.txt

# Start the MCP server first (in another terminal):
# cd ../task_manager_mcp && python server.py

# Then start this agent:
uvicorn serve:a2a_app --host localhost --port 8001
```

Agent card available at `http://localhost:8001/.well-known/agent.json`.

## Testing

```bash
# Check agent card
curl http://localhost:8001/.well-known/agent.json
```

Agent card is available at the deployed Cloud Run URL under `/a2a/task_manager_agent/.well-known/agent-card.json` post deployment.


## Command used

Ensure agent card is updated with the correct URL.

```bash
cd task_manager_agent
source .env
adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=Replace \
  --service_name=task-manager-agent \
  --with_ui \
  --a2a \
  . \
  -- \
  --service-account=$SERVICE_ACCOUNT 
```