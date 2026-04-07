"""AlloyDB database operations for the Task Manager MCP Server.

Provides CRUD operations and AlloyDB AI functions (semantic search,
ai.if() smart filtering, ai.generate() summaries) for the tasks table.
"""

import os
import json
import logging
from datetime import datetime

import pg8000
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("ALLOYDB_HOST", "127.0.0.1"),
    "port": int(os.getenv("ALLOYDB_PORT", "5432")),
    "user": os.getenv("ALLOYDB_USER", "postgres"),
    "password": os.getenv("ALLOYDB_PASSWORD", ""),
    "database": os.getenv("ALLOYDB_DATABASE", "task_manager"),
}


def _get_connection():
    return pg8000.connect(**DB_CONFIG)


def _rows_to_dicts(cursor, rows):
    columns = [desc[0] for desc in cursor.description]
    results = []
    for row in rows:
        results.append({
            col: (str(val) if val is not None else None)
            for col, val in zip(columns, row)
        })
    return results


# ---------------------------------------------------------------------------
# CRUD Operations
# ---------------------------------------------------------------------------

def create_task(title: str, description: str = None, assignee: str = None,
                priority: str = "MEDIUM", due_date: str = None,
                tags: str = None) -> dict:
    """Create a new task and auto-generate its vector embedding."""
    logger.info(f"create_task: {title}")
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # Insert task and generate embedding in one query
        cursor.execute("""
            INSERT INTO tasks (title, description, assignee, priority, status, due_date, tags, title_embedding)
            VALUES (%s, %s, %s, %s, 'open', %s, %s,
                    embedding('text-embedding-005', %s || ' ' || COALESCE(%s, '')))
            RETURNING task_id, title, assignee, priority, status, due_date, tags, created_at
        """, (title, description, assignee, priority, due_date, tags, title, description))

        row = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        result = {col: (str(val) if val is not None else None) for col, val in zip(columns, row)}
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "task": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def list_tasks(status: str = None, priority: str = None,
               assignee: str = None, due_before: str = None) -> dict:
    """List tasks with optional filters."""
    logger.info(f"list_tasks: status={status}, priority={priority}, assignee={assignee}")
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        query = "SELECT task_id, title, description, assignee, priority, status, due_date, tags, created_at FROM tasks WHERE 1=1"
        params = []

        if status:
            query += " AND status = %s"
            params.append(status)
        if priority:
            query += " AND priority = %s"
            params.append(priority)
        if assignee:
            query += " AND assignee = %s"
            params.append(assignee)
        if due_before:
            query += " AND due_date <= %s"
            params.append(due_before)

        query += " ORDER BY CASE priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 3 END, due_date ASC NULLS LAST"

        cursor.execute(query, params)
        results = _rows_to_dicts(cursor, cursor.fetchall())
        cursor.close()
        conn.close()
        return {"status": "success", "count": len(results), "tasks": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def update_task(task_id: int, title: str = None, status: str = None,
                priority: str = None, due_date: str = None,
                assignee: str = None, description: str = None) -> dict:
    """Update a task. Re-generates embedding if title or description changes."""
    logger.info(f"update_task: task_id={task_id}")
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        sets = ["updated_at = NOW()"]
        params = []

        if title is not None:
            sets.append("title = %s")
            params.append(title)
        if description is not None:
            sets.append("description = %s")
            params.append(description)
        if status is not None:
            sets.append("status = %s")
            params.append(status)
        if priority is not None:
            sets.append("priority = %s")
            params.append(priority)
        if due_date is not None:
            sets.append("due_date = %s")
            params.append(due_date)
        if assignee is not None:
            sets.append("assignee = %s")
            params.append(assignee)

        # Re-embed if title or description changed
        if title is not None or description is not None:
            sets.append("title_embedding = embedding('text-embedding-005', COALESCE(%s, title) || ' ' || COALESCE(%s, description, ''))")
            params.append(title)
            params.append(description)

        params.append(task_id)
        query = f"UPDATE tasks SET {', '.join(sets)} WHERE task_id = %s RETURNING task_id, title, assignee, priority, status, due_date"

        cursor.execute(query, params)
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return {"status": "error", "error": f"Task {task_id} not found."}

        columns = [desc[0] for desc in cursor.description]
        result = {col: (str(val) if val is not None else None) for col, val in zip(columns, row)}
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "task": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def delete_task(task_id: int) -> dict:
    """Delete a task by ID."""
    logger.info(f"delete_task: task_id={task_id}")
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE task_id = %s RETURNING task_id, title", (task_id,))
        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        if not row:
            return {"status": "error", "error": f"Task {task_id} not found."}
        return {"status": "success", "deleted": {"task_id": str(row[0]), "title": row[1]}}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# AlloyDB AI Operations
# ---------------------------------------------------------------------------

def semantic_search_tasks(query: str, top_k: int = 5) -> dict:
    """Search tasks using vector embeddings and cosine distance.

    Uses AlloyDB's embedding() function with text-embedding-005 and
    pgvector's <=> operator for semantic similarity ranking.
    """
    logger.info(f"semantic_search_tasks: query='{query}', top_k={top_k}")
    top_k = min(max(1, top_k), 20)
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT task_id, title, description, assignee, priority, status, due_date, tags,
                    title_embedding <=> embedding('text-embedding-005', %s)::vector AS distance  
            FROM tasks
            ORDER BY distance
            LIMIT %s
        """, (query, top_k))
        results = _rows_to_dicts(cursor, cursor.fetchall())
        cursor.close()
        conn.close()
        return {"status": "success", "query": query, "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def smart_filter_tasks(condition: str) -> dict:
    """Filter tasks using AlloyDB AI's ai.if() with a natural language condition.

    The ai.if() operator sends each row's data to a Gemini model and returns
    true/false based on the condition. Powerful for semantic filtering like
    "at risk of missing deadline" or "frontend-related task".
    """
    logger.info(f"smart_filter_tasks: condition='{condition}'")
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("SET google_ml_integration.enable_ai_query_engine = on")
        cursor.execute("""
            SELECT task_id, title, description, assignee, priority, status, due_date, tags
            FROM tasks
            WHERE ai.if(
                %s || ' Context: Task titled "' || title || '"'
                || ', description: ' || COALESCE(description, 'none')
                || ', assignee: ' || COALESCE(assignee, 'unassigned')
                || ', priority: ' || priority
                || ', status: ' || status
                || ', due: ' || COALESCE(due_date::text, 'no date')
                || ', tags: ' || COALESCE(tags, 'none')
            )
            LIMIT 20
        """, (condition,))
        results = _rows_to_dicts(cursor, cursor.fetchall())
        cursor.close()
        conn.close()
        return {"status": "success", "condition": condition, "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def generate_task_summary(scope: str = "all open") -> dict:
    """Generate a natural language summary of tasks using AlloyDB AI's ai.generate().

    The ai.generate() operator sends task data to a Gemini model and returns
    generated text. Use for standup summaries, status reports, etc.
    """
    logger.info(f"generate_task_summary: scope='{scope}'")
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("SET google_ml_integration.enable_ai_query_engine = on")

        # Build scope filter
        scope_lower = scope.lower()
        where_clause = "WHERE 1=1"
        if "open" in scope_lower:
            where_clause = "WHERE status = 'open'"
        elif "in_progress" in scope_lower or "in progress" in scope_lower:
            where_clause = "WHERE status = 'in_progress'"
        elif "done" in scope_lower or "completed" in scope_lower:
            where_clause = "WHERE status = 'done'"

        if "high" in scope_lower:
            where_clause += " AND priority = 'HIGH'"

        # Aggregate task data and generate summary
        cursor.execute(f"""
            SELECT ai.generate(
                'Generate a concise project status summary for a standup meeting based on these tasks. '
                || 'Group by assignee and highlight anything urgent or overdue. Today is {datetime.now().strftime("%Y-%m-%d")}. '
                || 'Tasks: ' || string_agg(
                    '- [' || priority || '/' || status || '] ' || title
                    || ' (assigned to ' || COALESCE(assignee, 'unassigned')
                    || ', due ' || COALESCE(due_date::text, 'no date') || ')',
                    '; '
                )
            ) AS summary
            FROM tasks
            {where_clause}
        """)
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row or not row[0]:
            return {"status": "success", "summary": "No tasks found matching the scope."}
        return {"status": "success", "scope": scope, "summary": str(row[0])}
    except Exception as e:
        return {"status": "error", "error": str(e)}
