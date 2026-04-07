"""
AlloyDB Tasks Database Setup Script

Creates the tasks table with AlloyDB AI capabilities (pgvector embeddings,
google_ml_integration for ai.if() and ai.generate()) and seeds sample data
for the Task Manager MCP Server demo.

Prerequisites:
  1. AlloyDB instance running and accessible (via Auth Proxy or direct IP)
  2. AlloyDB AI / Vertex AI integration enabled on the cluster
  3. pip install pg8000 python-dotenv
  4. .env file with ALLOYDB_* connection details

Usage:
  python setup_tasks_db.py
"""

import os
import sys
import pg8000
from dotenv import load_dotenv

load_dotenv()

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


SEED_SQL = """
INSERT INTO tasks (title, description, assignee, priority, status, due_date, tags) VALUES
('Implement checkout frontend rewrite',
 'Rewrite the checkout page using the new React component library. Must support mobile responsive layout and new payment form.',
 'Ankit', 'HIGH', 'open', '2026-04-10', 'frontend,checkout,react'),

('Build checkout backend APIs',
 'Create REST APIs for the new checkout flow: cart validation, payment processing, order confirmation. Integrate with Stripe.',
 'Meera', 'HIGH', 'open', '2026-04-10', 'backend,checkout,api'),

('Update project status deck',
 'Refresh the quarterly project status presentation with latest metrics, milestones, and risk items for the client review.',
 'Priya', 'MEDIUM', 'done', '2026-03-30', 'documentation,client'),

('Prepare demo environment with test data',
 'Set up the staging environment with realistic test data for the upcoming client demo. Include sample orders and user accounts.',
 'Ankit', 'MEDIUM', 'open', '2026-04-02', 'demo,staging,testing'),

('Fix mobile responsiveness issues on dashboard',
 'The analytics dashboard breaks on screens below 768px. Fix the grid layout and chart sizing for mobile viewports.',
 'Ankit', 'HIGH', 'in_progress', '2026-04-05', 'frontend,mobile,bugfix'),

('Set up CI/CD pipeline for new microservice',
 'Configure GitHub Actions workflow for the payments microservice: build, test, deploy to staging on PR merge.',
 'Rahul', 'MEDIUM', 'open', '2026-04-08', 'devops,cicd,payments'),

('Review and merge PR #342 for auth module',
 'Code review Rahul''s pull request for the OAuth2 integration. Check security implications and test coverage.',
 'Priya', 'HIGH', 'open', '2026-03-31', 'code-review,auth,security'),

('Reply to vendor email about licensing',
 'Respond to the software licensing vendor about the enterprise agreement renewal. Check with legal on terms.',
 'Priya', 'MEDIUM', 'open', '2026-03-31', 'admin,vendor,licensing'),

('Organize shared drive folders',
 'Clean up and restructure the team shared drive. Archive old project folders, create standard templates directory.',
 'Priya', 'LOW', 'open', '2026-04-15', 'admin,organization'),

('Write API documentation for payments endpoint',
 'Document the new payment processing APIs: request/response schemas, error codes, authentication, rate limits.',
 'Meera', 'MEDIUM', 'in_progress', '2026-04-07', 'documentation,api,payments'),

('Investigate production memory leak',
 'The order service shows increasing memory usage over 48 hours. Profile heap dumps and identify the leak source.',
 'Rahul', 'HIGH', 'in_progress', '2026-04-01', 'bugfix,production,backend'),

('Share revised timeline with client by end of month',
 'Send the updated project timeline to John at the client. Include the new milestones for the dashboard and mobile fixes.',
 'Priya', 'HIGH', 'open', '2026-03-30', 'client,timeline,communication'),

('Add unit tests for cart validation logic',
 'Write comprehensive unit tests for the cart validation module: edge cases for discounts, tax calculation, inventory checks.',
 'Meera', 'LOW', 'open', '2026-04-12', 'testing,backend,checkout'),

('Deploy monitoring dashboards for new services',
 'Set up Grafana dashboards for the payments and checkout microservices. Include latency, error rate, and throughput panels.',
 'Rahul', 'MEDIUM', 'open', '2026-04-10', 'devops,monitoring,grafana'),

('Security audit of user authentication flow',
 'Conduct a security review of the entire auth flow: token storage, session management, CSRF protection, rate limiting.',
 'Rahul', 'HIGH', 'open', '2026-04-05', 'security,auth,audit');
"""


def _execute_sql_block(cursor, sql_block):
    """Execute a block of SQL statements separated by semicolons."""
    for raw_statement in sql_block.split(";"):
        stripped = raw_statement.strip()
        if not stripped:
            continue
        meaningful_lines = [
            line for line in stripped.split("\n")
            if line.strip() and not line.strip().startswith("--")
        ]
        if not meaningful_lines:
            continue
        try:
            cursor.execute(stripped)
        except Exception as e:
            first_line = meaningful_lines[0].strip()[:80]
            print(f"\n  ERROR executing: {first_line}...")
            raise


def main():
    print("=" * 60)
    print("AlloyDB Setup — Task Manager Database")
    print("=" * 60)

    if not DB_PASSWORD:
        print("\nERROR: Set ALLOYDB_PASSWORD in .env before running this script.")
        sys.exit(1)

    print(f"\nConnecting to AlloyDB at {DB_HOST}:{DB_PORT}...")

    try:
        # Ensure database exists
        print(f"Ensuring database '{DB_NAME}' exists...")
        admin_conn = pg8000.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
            database="postgres",
        )
        admin_conn.autocommit = True
        admin_cursor = admin_conn.cursor()

        admin_cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,)
        )
        if admin_cursor.fetchone():
            print(f"  Database '{DB_NAME}' already exists.")
        else:
            admin_cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"  Database '{DB_NAME}' created.")

        admin_cursor.close()
        admin_conn.close()

        # Connect to target database
        print(f"\nConnecting to database '{DB_NAME}'...")
        conn = pg8000.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME,
        )
        conn.autocommit = True
        cursor = conn.cursor()
        print("Connected!\n")

        # Create schema
        print("Creating tasks table...")
        _execute_sql_block(cursor, SCHEMA_SQL)
        print("  - extensions: vector, google_ml_integration")
        print("  - tasks table with indexes")

        # Seed data
        print("\nInserting seed data (15 tasks)...")
        _execute_sql_block(cursor, SEED_SQL)

        # Verify
        cursor.execute("SELECT COUNT(*) FROM tasks")
        count = cursor.fetchone()[0]
        print(f"  tasks: {count} rows")

        # Generate embeddings
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

        # Create vector index (needs rows to exist first)
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
        print("Setup complete! Task Manager database is ready.")
        print("=" * 60)
        print("\nNext: Start the MCP server with `python task_manager_mcp/server.py`")

    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nTroubleshooting:")
        print("  - Is AlloyDB reachable? (via Auth Proxy or VPC)")
        print("  - Check ALLOYDB_* env vars in .env")
        print("  - Ensure Vertex AI API is enabled on the cluster")
        sys.exit(1)


if __name__ == "__main__":
    main()
