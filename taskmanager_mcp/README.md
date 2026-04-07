# Task Manager MCP Server

Custom-built MCP server backed by AlloyDB with AI capabilities. Exposes 7 tools via Streamable HTTP transport:

- **CRUD**: `create_task`, `list_tasks`, `update_task`, `delete_task`
- **AlloyDB AI**: `semantic_search_tasks` (vector embeddings), `smart_filter_tasks` (ai.if), `generate_task_summary` (ai.generate)

## Prerequisites

- Python 3.13+
- AlloyDB instance with `vector` and `google_ml_integration` extensions
- Tasks table created via `setup_tasks_db.py` (in parent directory)

## Environment Variables

```bash
# AlloyDB connection details
ALLOYDB_HOST=YourAlloyDBHostHere
ALLOYDB_PORT=5432
ALLOYDB_USER=postgres
ALLOYDB_PASSWORD=YourPasswordHere
ALLOYDB_DATABASE=task_manager
MCP_SERVER_PORT=8010          # optional, default 8010

# Google Cloud
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=YourProjectNameHere
GOOGLE_CLOUD_LOCATION=DesiredLocationHere
PROJECT_ID=ProjectIDHere
PROJECT_NUMBER=ProjectNumberHere
SA_NAME=proj1-service
SERVICE_ACCOUNT=proj1-service@ProjectIDHere.iam.gserviceaccount.com
MODEL="gemini-2.5-flash"
```

## Local Run

```bash
cd task_manager_mcp
pip install -r requirements.txt
python server.py
```

Server starts at `http://localhost:8010/mcp`.

## Testing

```bash
# List tools
curl -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Command used

```bash
cd taskmanager_mcp
source .env
gcloud run deploy taskmanager-mcp \
  --source . \
  --project=$PROJECT_ID \
  --region=Replace \
  --allow-unauthenticated \
  --set-env-vars "MCP_SERVER_PORT=8080" \
  --port 8080

```
> **Note:** On Cloud Run, set `MCP_SERVER_PORT=8080` since Cloud Run routes traffic to the `PORT` env var (default 8080). The Dockerfile uses `python server.py` which reads `MCP_SERVER_PORT`.

