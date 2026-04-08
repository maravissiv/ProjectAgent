# Project

Project done for hackathon associated with Google Cloud - Generative AI.

Multi-Agent Project Manager Assistant built with Google ADK, A2A protocol, and Vertex AI (Gemini).

## Architecture

```mermaid
graph TD
    User([User]) --> Orchestrator["Orchestrator Agent\n:8000\n(A2A root)"]

    Orchestrator -- A2A --> TaskAgent["Task Manager Agent\n:8001"]
    Orchestrator -- A2A --> CalendarAgent["Calendar Agent\n:8002"]
    Orchestrator -- A2A --> NotesAgent["Notes Agent\n:8003"]

    TaskAgent -- MCP --> MCP["Task Manager MCP\n:8010"]
    MCP --> AlloyDB[("AlloyDB + AI\n(primary)")]
    MCP --> FirestoreTasks[("Firestore + Gemini\n(fallback)")]
    CalendarAgent --> Firestore[("Firestore")]
    NotesAgent --> GCS[("Cloud Storage\n(GCS)")]

    style Orchestrator fill:#4285F4,color:#fff
    style TaskAgent fill:#EA4335,color:#fff
    style CalendarAgent fill:#FBBC04,color:#000
    style NotesAgent fill:#34A853,color:#fff
    style MCP fill:#EA4335,color:#fff
    style FirestoreTasks fill:#EA4335,color:#fff,stroke-dasharray: 5 5
```

## Agents

| Service | Port | Description |
|---|---|---|
| **Orchestrator Agent** | 8000 | Root agent that coordinates all sub-agents. Delegates user requests to the task, calendar, and notes agents via A2A, handling fan-out, sequential chaining, and cross-agent workflows. |
| **Task Manager Agent** | 8001 | Manages tasks (CRUD, semantic search, smart filtering, summaries) by connecting to the Task Manager MCP Server. |
| **Calendar Agent** | 8002 | Schedule management agent backed by Firestore. Supports creating, listing, searching, and updating events, plus free-slot detection. Pre-seeded with demo data. |
| **Notes Agent** | 8003 | Markdown note management agent backed by Google Cloud Storage. Supports saving, reading, listing, and searching notes. |
| **Task Manager MCP** | 8010 | MCP server (Streamable HTTP) with **dual-backend** support. Tries AlloyDB at startup; falls back to Firestore + Gemini API if unreachable. Exposes task CRUD plus AI tools (vector search, smart filter, summary generation). |
