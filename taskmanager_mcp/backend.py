"""Backend selector for the Task Manager MCP Server.

Probes AlloyDB at import time. If reachable, uses the AlloyDB backend (db.py).
Otherwise, falls back to the Firestore + Gemini API backend (db_firestore.py).

Both modules export identical function signatures so the rest of the server
is backend-agnostic.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _probe_alloydb() -> bool:
    """Try connecting to AlloyDB. Return True if reachable."""
    password = os.getenv("ALLOYDB_PASSWORD", "")
    if not password:
        logger.info("ALLOYDB_PASSWORD not set — skipping AlloyDB probe")
        return False

    try:
        import pg8000
        conn = pg8000.connect(
            host=os.getenv("ALLOYDB_HOST", "127.0.0.1"),
            port=int(os.getenv("ALLOYDB_PORT", "5432")),
            user=os.getenv("ALLOYDB_USER", "postgres"),
            password=password,
            database=os.getenv("ALLOYDB_DATABASE", "task_manager"),
        )
        conn.close()
        return True
    except Exception as e:
        logger.warning("AlloyDB not reachable (%s), will use Firestore backend", e)
        return False


if _probe_alloydb():
    logger.info("Backend: AlloyDB")
    from db import (  # noqa: F401
        create_task,
        list_tasks,
        update_task,
        delete_task,
        semantic_search_tasks,
        smart_filter_tasks,
        generate_task_summary,
    )
    BACKEND = "alloydb"
else:
    logger.info("Backend: Firestore + Gemini API")
    from db_firestore import (  # noqa: F401
        create_task,
        list_tasks,
        update_task,
        delete_task,
        semantic_search_tasks,
        smart_filter_tasks,
        generate_task_summary,
    )
    BACKEND = "firestore"
