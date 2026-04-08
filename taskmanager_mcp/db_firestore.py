"""Firestore + Gemini API database operations for the Task Manager MCP Server.

Drop-in replacement for db.py (AlloyDB). Provides identical function signatures
using Firestore for persistence and google-genai for AI features (embeddings,
smart filtering, summary generation).
"""

import os
import json
import logging
from datetime import datetime

import numpy as np
from dotenv import load_dotenv
from google.cloud import firestore
from google import genai

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Firestore Configuration
# ---------------------------------------------------------------------------

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
FIRESTORE_DATABASEID = os.getenv("FIRESTORE_TASKS_DATABASEID", "genaihackathon")
FIRESTORE_COLLECTION = os.getenv("FIRESTORE_TASKS_COLLECTION", "tasks_hackathon")

db = firestore.Client(project=project_id, database=FIRESTORE_DATABASEID)
tasks_ref = db.collection(FIRESTORE_COLLECTION)
counters_ref = db.collection("_meta")

# ---------------------------------------------------------------------------
# Gemini / Vertex AI client
# ---------------------------------------------------------------------------

genai_client = genai.Client(vertexai=True, project=project_id,
                            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"))
EMBEDDING_MODEL = "text-embedding-004"
GEMINI_MODEL = os.getenv("MODEL", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_task_id() -> int:
    """Atomically increment and return the next task_id using a Firestore counter."""
    counter_ref = counters_ref.document("task_counter")
    @firestore.transactional
    def _increment(transaction):
        snap = counter_ref.get(transaction=transaction)
        current = snap.get("value") if snap.exists else 0
        next_val = current + 1
        transaction.set(counter_ref, {"value": next_val})
        return next_val
    return _increment(db.transaction())


def _generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for the given text using Vertex AI."""
    try:
        result = genai_client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
        )
        return result.embeddings[0].values
    except Exception as e:
        logger.error("Embedding generation failed: %s", e)
        return []


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a, dtype=np.float32)
    b_arr = np.array(b, dtype=np.float32)
    dot = np.dot(a_arr, b_arr)
    norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def _doc_to_task(doc) -> dict:
    """Convert a Firestore document to a clean task dict (no embedding, no Sentinel)."""
    data = doc.to_dict()
    data.pop("title_embedding", None)
    created_at = data.pop("created_at", None)
    if created_at and not isinstance(created_at, type(firestore.SERVER_TIMESTAMP)):
        data["created_at"] = str(created_at)
    updated_at = data.pop("updated_at", None)
    if updated_at and not isinstance(updated_at, type(firestore.SERVER_TIMESTAMP)):
        data["updated_at"] = str(updated_at)
    return {k: (str(v) if v is not None else None) for k, v in data.items()}


def _priority_sort_key(task: dict) -> tuple:
    """Sort key: HIGH=1, MEDIUM=2, LOW=3, then by due_date ascending (nulls last)."""
    p_map = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
    p = p_map.get(task.get("priority", "MEDIUM"), 2)
    due = task.get("due_date") or "9999-99-99"
    return (p, due)


# ---------------------------------------------------------------------------
# CRUD Operations
# ---------------------------------------------------------------------------

def create_task(title: str, description: str = None, assignee: str = None,
                priority: str = "MEDIUM", due_date: str = None,
                tags: str = None) -> dict:
    """Create a new task with auto-generated embedding."""
    logger.info("create_task: %s", title)
    try:
        task_id = _next_task_id()
        embed_text = title + " " + (description or "")
        embedding = _generate_embedding(embed_text)

        task_data = {
            "task_id": task_id,
            "title": title,
            "description": description,
            "assignee": assignee,
            "priority": priority,
            "status": "open",
            "due_date": due_date,
            "tags": tags,
            "title_embedding": embedding,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        doc_ref = tasks_ref.document(str(task_id))
        doc_ref.set(task_data)

        created_doc = doc_ref.get()
        result = _doc_to_task(created_doc)
        return {"status": "success", "task": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def list_tasks(status: str = None, priority: str = None,
               assignee: str = None, due_before: str = None) -> dict:
    """List tasks with optional filters."""
    logger.info("list_tasks: status=%s, priority=%s, assignee=%s", status, priority, assignee)
    try:
        query = tasks_ref

        # Apply Firestore-native filters where possible
        if status:
            query = query.where("status", "==", status)
        if priority:
            query = query.where("priority", "==", priority)
        if assignee:
            query = query.where("assignee", "==", assignee)

        results = []
        for doc in query.stream():
            task = _doc_to_task(doc)
            # Apply due_before filter in Python (Firestore compound query limitations)
            if due_before and task.get("due_date"):
                if task["due_date"] > due_before:
                    continue
            results.append(task)

        results.sort(key=_priority_sort_key)
        return {"status": "success", "count": len(results), "tasks": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def update_task(task_id: int, title: str = None, status: str = None,
                priority: str = None, due_date: str = None,
                assignee: str = None, description: str = None) -> dict:
    """Update a task. Re-generates embedding if title or description changes."""
    logger.info("update_task: task_id=%s", task_id)
    try:
        doc_ref = tasks_ref.document(str(task_id))
        doc = doc_ref.get()
        if not doc.exists:
            return {"status": "error", "error": f"Task {task_id} not found."}

        updates = {"updated_at": firestore.SERVER_TIMESTAMP}
        if title is not None:
            updates["title"] = title
        if description is not None:
            updates["description"] = description
        if status is not None:
            updates["status"] = status
        if priority is not None:
            updates["priority"] = priority
        if due_date is not None:
            updates["due_date"] = due_date
        if assignee is not None:
            updates["assignee"] = assignee

        # Re-embed if title or description changed
        if title is not None or description is not None:
            current = doc.to_dict()
            new_title = title if title is not None else current.get("title", "")
            new_desc = description if description is not None else (current.get("description") or "")
            updates["title_embedding"] = _generate_embedding(new_title + " " + new_desc)

        doc_ref.update(updates)
        updated_doc = doc_ref.get()
        result = _doc_to_task(updated_doc)
        return {"status": "success", "task": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def delete_task(task_id: int) -> dict:
    """Delete a task by ID."""
    logger.info("delete_task: task_id=%s", task_id)
    try:
        doc_ref = tasks_ref.document(str(task_id))
        doc = doc_ref.get()
        if not doc.exists:
            return {"status": "error", "error": f"Task {task_id} not found."}

        data = doc.to_dict()
        doc_ref.delete()
        return {"status": "success", "deleted": {"task_id": str(task_id), "title": data.get("title")}}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# AI Operations (Gemini API replacements for AlloyDB AI)
# ---------------------------------------------------------------------------

def semantic_search_tasks(query: str, top_k: int = 5) -> dict:
    """Search tasks using vector embeddings and cosine similarity.

    Uses Vertex AI text-embedding-004 for embeddings and numpy for
    cosine distance ranking — equivalent to AlloyDB's embedding() + pgvector.
    """
    logger.info("semantic_search_tasks: query='%s', top_k=%s", query, top_k)
    top_k = min(max(1, top_k), 20)
    try:
        query_embedding = _generate_embedding(query)
        if not query_embedding:
            return {"status": "error", "error": "Failed to generate query embedding"}

        scored = []
        for doc in tasks_ref.stream():
            data = doc.to_dict()
            task_emb = data.get("title_embedding")
            if not task_emb:
                continue
            sim = _cosine_similarity(query_embedding, task_emb)
            task = _doc_to_task(doc)
            task["distance"] = str(round(1.0 - sim, 6))
            scored.append((sim, task))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [t for _, t in scored[:top_k]]
        return {"status": "success", "query": query, "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def smart_filter_tasks(condition: str) -> dict:
    """Filter tasks using Gemini with a natural language condition.

    Replaces AlloyDB AI's ai.if() — sends all tasks to Gemini and asks
    it to evaluate which ones match the condition.
    """
    logger.info("smart_filter_tasks: condition='%s'", condition)
    try:
        all_tasks = []
        for doc in tasks_ref.stream():
            task = _doc_to_task(doc)
            all_tasks.append(task)

        if not all_tasks:
            return {"status": "success", "condition": condition, "count": 0, "results": []}

        tasks_text = json.dumps(all_tasks, indent=2, default=str)
        prompt = f"""You are a task filtering assistant. Given the following list of tasks and a condition,
return ONLY a JSON array of task_id values (integers) for tasks that match the condition.

Condition: {condition}

Tasks:
{tasks_text}

Return ONLY a JSON array of matching task_id integers, e.g. [1, 3, 7]. No other text."""

        response = genai_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        response_text = response.text.strip()
        # Extract JSON array from response (handle markdown code blocks)
        if "```" in response_text:
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        matching_ids = json.loads(response_text)
        matching_ids_str = {str(tid) for tid in matching_ids}

        results = [t for t in all_tasks if t.get("task_id") in matching_ids_str]
        return {"status": "success", "condition": condition, "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def generate_task_summary(scope: str = "all open") -> dict:
    """Generate a natural language summary of tasks using Gemini.

    Replaces AlloyDB AI's ai.generate() — sends task data to Gemini
    for standup-style summary generation.
    """
    logger.info("generate_task_summary: scope='%s'", scope)
    try:
        # Build scope filter
        scope_lower = scope.lower()
        query = tasks_ref

        if "open" in scope_lower:
            query = query.where("status", "==", "open")
        elif "in_progress" in scope_lower or "in progress" in scope_lower:
            query = query.where("status", "==", "in_progress")
        elif "done" in scope_lower or "completed" in scope_lower:
            query = query.where("status", "==", "done")

        tasks = []
        for doc in query.stream():
            task = _doc_to_task(doc)
            # Apply high-priority filter in Python if needed
            if "high" in scope_lower and task.get("priority") != "HIGH":
                continue
            tasks.append(task)

        if not tasks:
            return {"status": "success", "summary": "No tasks found matching the scope."}

        tasks_text = "\n".join(
            f"- [{t.get('priority', 'MEDIUM')}/{t.get('status', 'open')}] {t.get('title', '')} "
            f"(assigned to {t.get('assignee') or 'unassigned'}, "
            f"due {t.get('due_date') or 'no date'})"
            for t in tasks
        )

        prompt = f"""Generate a concise project status summary for a standup meeting based on these tasks.
Group by assignee and highlight anything urgent or overdue. Today is {datetime.now().strftime("%Y-%m-%d")}.

Tasks:
{tasks_text}"""

        response = genai_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        summary = response.text.strip()
        return {"status": "success", "scope": scope, "summary": summary}
    except Exception as e:
        return {"status": "error", "error": str(e)}
