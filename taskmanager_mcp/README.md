# Task Manager MCP Server

Custom-built MCP server with AI capabilities and **dual-backend** support. Exposes 7 tools via Streamable HTTP transport:

- **CRUD**: `create_task`, `list_tasks`, `update_task`, `delete_task`
- **AI**: `semantic_search_tasks` (vector embeddings), `smart_filter_tasks` (AI condition), `generate_task_summary` (AI summary)

## Backends

The server automatically selects the backend at startup:

| Backend | Persistence | AI Features | When Used |
|---------|-------------|-------------|-----------|
| **AlloyDB** (primary) | PostgreSQL via pg8000 | AlloyDB AI: `embedding()`, `ai.if()`, `ai.generate()` | AlloyDB reachable |
| **Firestore** (fallback) | Google Cloud Firestore | Gemini API: `text-embedding-004`, `generate_content()` | AlloyDB unreachable |

Both backends expose **identical tool interfaces** — the agent and orchestrator are backend-agnostic.

## Architecture

```
backend.py          ← Probes AlloyDB, picks backend, re-exports functions
  ├── db.py         ← AlloyDB implementation (original)
  └── db_firestore.py ← Firestore + Gemini API implementation
server.py           ← MCP server (imports from backend.py)
```

## Prerequisites

- Python 3.13+
- **AlloyDB path**: AlloyDB instance with `vector` and `google_ml_integration` extensions
- **Firestore path**: GCP project with Firestore database and Vertex AI API enabled

## Environment Variables

```bash
# AlloyDB connection (primary — used if reachable)
ALLOYDB_HOST=YourAlloyDBHostHere
ALLOYDB_PORT=5432
ALLOYDB_USER=postgres
ALLOYDB_PASSWORD=YourPasswordHere
ALLOYDB_DATABASE=task_manager

# Firestore (fallback — used when AlloyDB is unreachable)
FIRESTORE_TASKS_DATABASEID=genaihackathon
FIRESTORE_TASKS_COLLECTION=tasks_hackathon

# Google Cloud (required for both backends)
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=YourProjectNameHere
GOOGLE_CLOUD_LOCATION=DesiredLocationHere
MCP_SERVER_PORT=8010          # optional, default 8010
MODEL="gemini-2.5-flash"
```

## Setup

```bash
# Install dependencies
cd taskmanager_mcp
pip install -r requirements.txt

# Seed sample data (auto-detects backend)
cd ..
python setup_db_tasks.py

# Start the MCP server
python taskmanager_mcp/server.py
```

Server starts at `http://localhost:8010/mcp`.

## Testing

```bash
# List tools
curl -X POST http://localhost:8010/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Cloud Run Deployment

```bash
cd taskmanager_mcp
source .env
gcloud run deploy taskmanager-mcp \
  --source . \
  --project=$PROJECT_ID \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars "MCP_SERVER_PORT=8080" \
  --port 8080
```

> **Note:** On Cloud Run, set `MCP_SERVER_PORT=8080` since Cloud Run routes traffic to port 8080 by default.
