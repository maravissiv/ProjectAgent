"""
Task Manager Database Setup Script — Dual Backend

Seeds 15 sample tasks into either AlloyDB or Firestore, depending on
which backend is available.

- AlloyDB path: Creates table with pgvector + google_ml_integration,
  generates embeddings via AlloyDB's embedding() function.
- Firestore path: Writes documents to Firestore, generates embeddings
  via Vertex AI text-embedding-004.

Prerequisites:
  pip install pg8000 google-cloud-firestore google-genai numpy python-dotenv

Usage:
  python setup_db_tasks.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Sample tasks (shared by both backends)
# ---------------------------------------------------------------------------

SEED_TASKS = [
    {"title": "Implement checkout frontend rewrite",
     "description": "Rewrite the checkout page using the new React component library. Must support mobile responsive layout and new payment form.",
     "assignee": "Ankit", "priority": "HIGH", "status": "open", "due_date": "2026-04-10", "tags": "frontend,checkout,react"},

    {"title": "Build checkout backend APIs",
     "description": "Create REST APIs for the new checkout flow: cart validation, payment processing, order confirmation. Integrate with Stripe.",
     "assignee": "Meera", "priority": "HIGH", "status": "open", "due_date": "2026-04-10", "tags": "backend,checkout,api"},

    {"title": "Update project status deck",
     "description": "Refresh the quarterly project status presentation with latest metrics, milestones, and risk items for the client review.",
     "assignee": "Priya", "priority": "MEDIUM", "status": "done", "due_date": "2026-03-30", "tags": "documentation,client"},

    {"title": "Prepare demo environment with test data",
     "description": "Set up the staging environment with realistic test data for the upcoming client demo. Include sample orders and user accounts.",
     "assignee": "Ankit", "priority": "MEDIUM", "status": "open", "due_date": "2026-04-02", "tags": "demo,staging,testing"},

    {"title": "Fix mobile responsiveness issues on dashboard",
     "description": "The analytics dashboard breaks on screens below 768px. Fix the grid layout and chart sizing for mobile viewports.",
     "assignee": "Ankit", "priority": "HIGH", "status": "in_progress", "due_date": "2026-04-05", "tags": "frontend,mobile,bugfix"},

    {"title": "Set up CI/CD pipeline for new microservice",
     "description": "Configure GitHub Actions workflow for the payments microservice: build, test, deploy to staging on PR merge.",
     "assignee": "Rahul", "priority": "MEDIUM", "status": "open", "due_date": "2026-04-08", "tags": "devops,cicd,payments"},

    {"title": "Review and merge PR #342 for auth module",
     "description": "Code review Rahul's pull request for the OAuth2 integration. Check security implications and test coverage.",
     "assignee": "Priya", "priority": "HIGH", "status": "open", "due_date": "2026-03-31", "tags": "code-review,auth,security"},

    {"title": "Reply to vendor email about licensing",
     "description": "Respond to the software licensing vendor about the enterprise agreement renewal. Check with legal on terms.",
     "assignee": "Priya", "priority": "MEDIUM", "status": "open", "due_date": "2026-03-31", "tags": "admin,vendor,licensing"},

    {"title": "Organize shared drive folders",
     "description": "Clean up and restructure the team shared drive. Archive old project folders, create standard templates directory.",
     "assignee": "Priya", "priority": "LOW", "status": "open", "due_date": "2026-04-15", "tags": "admin,organization"},

    {"title": "Write API documentation for payments endpoint",
     "description": "Document the new payment processing APIs: request/response schemas, error codes, authentication, rate limits.",
     "assignee": "Meera", "priority": "MEDIUM", "status": "in_progress", "due_date": "2026-04-07", "tags": "documentation,api,payments"},

    {"title": "Investigate production memory leak",
     "description": "The order service shows increasing memory usage over 48 hours. Profile heap dumps and identify the leak source.",
     "assignee": "Rahul", "priority": "HIGH", "status": "in_progress", "due_date": "2026-04-01", "tags": "bugfix,production,backend"},

    {"title": "Share revised timeline with client by end of month",
     "description": "Send the updated project timeline to John at the client. Include the new milestones for the dashboard and mobile fixes.",
     "assignee": "Priya", "priority": "HIGH", "status": "open", "due_date": "2026-03-30", "tags": "client,timeline,communication"},

    {"title": "Add unit tests for cart validation logic",
     "description": "Write comprehensive unit tests for the cart validation module: edge cases for discounts, tax calculation, inventory checks.",
     "assignee": "Meera", "priority": "LOW", "status": "open", "due_date": "2026-04-12", "tags": "testing,backend,checkout"},

    {"title": "Deploy monitoring dashboards for new services",
     "description": "Set up Grafana dashboards for the payments and checkout microservices. Include latency, error rate, and throughput panels.",
     "assignee": "Rahul", "priority": "MEDIUM", "status": "open", "due_date": "2026-04-10", "tags": "devops,monitoring,grafana"},

    {"title": "Security audit of user authentication flow",
     "description": "Conduct a security review of the entire auth flow: token storage, session management, CSRF protection, rate limiting.",
     "assignee": "Rahul", "priority": "HIGH", "status": "open", "due_date": "2026-04-05", "tags": "security,auth,audit"},
]


# ---------------------------------------------------------------------------
# AlloyDB Setup
# ---------------------------------------------------------------------------

def _probe_alloydb() -> bool:
    password = os.getenv("ALLOYDB_PASSWORD", "")
    if not password:
        return False
    try:
        import pg8000
        conn = pg8000.connect(
            host=os.getenv("ALLOYDB_HOST", "127.0.0.1"),
            port=int(os.getenv("ALLOYDB_PORT", "5432")),
            user=os.getenv("ALLOYDB_USER", "postgres"),
            password=password,
            database="postgres",
        )
        conn.close()
        return True
    except Exception:
        return False


def setup_alloydb():
    """Original AlloyDB setup — create schema + seed with embeddings."""
    import pg8000

    DB_HOST = os.getenv("ALLOYDB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("ALLOYDB_PORT", "5432"))
    DB_USER = os.getenv("ALLOYDB_USER", "postgres")
    DB_PASSWORD = os.getenv("ALLOYDB_PASSWORD", "")
    DB_NAME = os.getenv("ALLOYDB_DATABASE", "task_manager")

    SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS google_ml_integration VERSION '1.5.2' CASCADE;

SET google_ml_integration.enable_ai_query_engine = on;

DROP TABLE IF EXISTS tasks CASCADE;

CREATE TABLE tasks (
    task_id         SERIAL PRIMARY KEY,
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    assignee        VARCHAR(100),
    priority        VARCHAR(10) NOT NULL CHECK (priority IN ('HIGH', 'MEDIUM', 'LOW')),
    status          VARCHAR(20) NOT NULL CHECK (status IN ('open', 'in_progress', 'done')),
    due_date        DATE,
    tags            TEXT,
    title_embedding vector(768),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE tasks IS 'Project tasks with AlloyDB AI vector embeddings for semantic search';
COMMENT ON COLUMN tasks.title_embedding IS 'Vector embedding of title+description via text-embedding-005';
COMMENT ON COLUMN tasks.tags IS 'Comma-separated tags for categorization';

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_assignee ON tasks(assignee);
CREATE INDEX idx_tasks_due ON tasks(due_date);
"""

    # Build INSERT SQL from SEED_TASKS
    values = []
    for t in SEED_TASKS:
        vals = (
            t["title"], t["description"], t["assignee"], t["priority"],
            t["status"], t["due_date"], t["tags"]
        )
        escaped = []
        for v in vals:
            escaped.append("'" + v.replace("'", "''") + "'" if v else "NULL")
        values.append(f"({', '.join(escaped)})")

    seed_sql = ("INSERT INTO tasks (title, description, assignee, priority, status, due_date, tags) VALUES\n"
                + ",\n".join(values))

    def _execute_sql_block(cursor, sql_block):
        for raw in sql_block.split(";"):
            stripped = raw.strip()
            if not stripped:
                continue
            meaningful = [l for l in stripped.split("\n") if l.strip() and not l.strip().startswith("--")]
            if not meaningful:
                continue
            cursor.execute(stripped)

    print("=" * 60)
    print("AlloyDB Setup — Task Manager Database")
    print("=" * 60)

    print(f"\nConnecting to AlloyDB at {DB_HOST}:{DB_PORT}...")

    # Ensure database exists
    print(f"Ensuring database '{DB_NAME}' exists...")
    admin_conn = pg8000.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database="postgres")
    admin_conn.autocommit = True
    admin_cursor = admin_conn.cursor()
    admin_cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
    if admin_cursor.fetchone():
        print(f"  Database '{DB_NAME}' already exists.")
    else:
        admin_cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
        print(f"  Database '{DB_NAME}' created.")
    admin_cursor.close()
    admin_conn.close()

    # Connect to target database
    print(f"\nConnecting to database '{DB_NAME}'...")
    conn = pg8000.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
    conn.autocommit = True
    cursor = conn.cursor()
    print("Connected!\n")

    print("Creating tasks table...")
    _execute_sql_block(cursor, SCHEMA_SQL)
    print("  - extensions: vector, google_ml_integration")
    print("  - tasks table with indexes")

    print("\nInserting seed data (15 tasks)...")
    _execute_sql_block(cursor, seed_sql)

    cursor.execute("SELECT COUNT(*) FROM tasks")
    count = cursor.fetchone()[0]
    print(f"  tasks: {count} rows")

    print("\nGenerating vector embeddings for tasks...")
    print("  Using model: text-embedding-005")
    cursor.execute("""
        UPDATE tasks
        SET title_embedding = embedding(
            'text-embedding-005',
            title || ' ' || COALESCE(description, '')
        )
        WHERE title_embedding IS NULL
    """)
    print("  Embeddings generated for all tasks.")

    print("  Creating IVFFlat vector index...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_embedding
        ON tasks USING ivfflat (title_embedding vector_cosine_ops)
        WITH (lists = 5)
    """)
    print("  Vector index created.")

    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("Setup complete! Task Manager database is ready (AlloyDB).")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Firestore Setup
# ---------------------------------------------------------------------------

def setup_firestore():
    """Firestore setup — seed tasks with Vertex AI embeddings."""
    from google.cloud import firestore as fs
    from google import genai

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    db_id = os.getenv("FIRESTORE_TASKS_DATABASEID", "genaihackathon")
    collection_name = os.getenv("FIRESTORE_TASKS_COLLECTION", "tasks_hackathon")

    print("=" * 60)
    print("Firestore Setup — Task Manager Database")
    print("=" * 60)

    print(f"\nProject: {project_id}")
    print(f"Database: {db_id}")
    print(f"Collection: {collection_name}")

    db = fs.Client(project=project_id, database=db_id)
    tasks_ref = db.collection(collection_name)
    counters_ref = db.collection("_meta")

    # Check if already seeded
    existing = list(tasks_ref.limit(1).stream())
    if existing:
        print(f"\nCollection '{collection_name}' already has data. Skipping seed.")
        count = len(list(tasks_ref.stream()))
        print(f"  Existing tasks: {count}")
        print("\nSetup complete! (no changes made)")
        return

    # Init Gemini client for embeddings
    genai_client = genai.Client(
        vertexai=True, project=project_id,
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )
    EMBEDDING_MODEL = "text-embedding-004"

    print(f"\nSeeding {len(SEED_TASKS)} tasks into Firestore...")
    print(f"  Generating embeddings with {EMBEDDING_MODEL}...")

    for i, task in enumerate(SEED_TASKS, start=1):
        task_id = i

        # Generate embedding
        embed_text = task["title"] + " " + (task.get("description") or "")
        try:
            result = genai_client.models.embed_content(model=EMBEDDING_MODEL, contents=embed_text)
            embedding = result.embeddings[0].values
        except Exception as e:
            print(f"  WARNING: Embedding failed for task {task_id}: {e}")
            embedding = []

        doc_data = {
            "task_id": task_id,
            "title": task["title"],
            "description": task.get("description"),
            "assignee": task.get("assignee"),
            "priority": task["priority"],
            "status": task["status"],
            "due_date": task.get("due_date"),
            "tags": task.get("tags"),
            "title_embedding": embedding,
            "created_at": fs.SERVER_TIMESTAMP,
            "updated_at": fs.SERVER_TIMESTAMP,
        }

        tasks_ref.document(str(task_id)).set(doc_data)
        print(f"  [{task_id:2d}/15] {task['title'][:60]}")

    # Set counter
    counters_ref.document("task_counter").set({"value": len(SEED_TASKS)})
    print(f"\n  Counter set to {len(SEED_TASKS)}")

    print("\n" + "=" * 60)
    print("Setup complete! Task Manager database is ready (Firestore).")
    print("=" * 60)
    print(f"\nNext: Start the MCP server with `python taskmanager_mcp/server.py`")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if _probe_alloydb():
        print("AlloyDB is reachable — using AlloyDB backend.\n")
        setup_alloydb()
    else:
        print("AlloyDB not reachable — using Firestore backend.\n")
        setup_firestore()


if __name__ == "__main__":
    main()
