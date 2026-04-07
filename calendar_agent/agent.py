"""Calendar Agent — ADK agent for schedule management backed by Firestore.

Uses native function tools with Firestore for persistent event storage.
Events survive Cloud Run cold starts and scale-to-zero.
"""

import os
from datetime import datetime
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.cloud import firestore
from google.adk.apps.app import App
from google.genai.types import HttpRetryOptions
import logging
import google.cloud.logging

load_dotenv()

model_name = os.getenv("MODEL", "gemini-2.5-flash")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Retry configuration for Gemini model calls
RETRY_OPTIONS = HttpRetryOptions(initial_delay=1, max_delay=3, attempts=30)


# ---------------------------------------------------------------------------
# Firestore Configuration
# ---------------------------------------------------------------------------

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
FIRESTORE_DATABASEID = os.getenv("FIRESTORE_CALENDAR_DATABASEID", "genaihackathon");
FIRESTORE_COLLECTION = os.getenv("FIRESTORE_CALENDAR_COLLECTION", "calendar_events_hackathon")

db = firestore.Client(project=project_id,database=FIRESTORE_DATABASEID)
events_ref = db.collection(FIRESTORE_COLLECTION)

# ---------------------------------------------------------------------------
# Seed Demo Events (only if collection is empty)
# ---------------------------------------------------------------------------

def _seed_demo_events():
    """Seed demo events for the 'Day in the Life of a PM' scenario.

    Dates are computed relative to today so the demo works on any day.
    """
    existing = list(events_ref.limit(1).stream())
    if existing:
        logger.info("Firestore collection '%s' already has data, skipping seed.", FIRESTORE_COLLECTION)
        return

    from datetime import timedelta
    today = datetime.now().date()
    d = lambda offset: (today + timedelta(days=offset)).strftime("%Y-%m-%d")

    logger.info("Seeding demo events into Firestore collection '%s'...", FIRESTORE_COLLECTION)
    seed_events = [
        # ===== PAST 2 WEEKS (for Pattern 5: sprint retro) =====

        # --- Day -13 (start of sprint) ---
        {"title": "Sprint Planning", "date": d(-13), "start_time": "09:30", "end_time": "10:30",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Sprint kickoff — planned checkout rewrite, mobile fixes, memory leak investigation, and client deliverables."},

        # --- Day -12 ---
        {"title": "Daily Standup", "date": d(-12), "start_time": "09:00", "end_time": "09:15",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Daily sync — Ankit started checkout wireframes, Meera on Stripe webhook."},

        # --- Day -10 ---
        {"title": "Daily Standup", "date": d(-10), "start_time": "09:00", "end_time": "09:15",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Daily sync — Rahul fixing Terraform drift, Meera finishing Stripe webhook."},
        {"title": "Design Review — Checkout Wireframes", "date": d(-10), "start_time": "14:00", "end_time": "15:00",
         "attendees": "Priya, Ankit, John (client)", "description": "Reviewed Ankit's checkout page wireframes with client. Approved with minor color tweaks."},

        # --- Day -8 ---
        {"title": "Daily Standup", "date": d(-8), "start_time": "09:00", "end_time": "09:15",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Daily sync — Ankit wireframes done, Meera starting integration tests."},
        {"title": "1:1 with Rahul", "date": d(-8), "start_time": "11:00", "end_time": "11:30",
         "attendees": "Priya, Rahul", "description": "Discussed staging DB setup and Terraform drift resolution. Rahul needs production access for memory leak."},

        # --- Day -7 ---
        {"title": "Sprint Mid-Point Review", "date": d(-7), "start_time": "10:00", "end_time": "10:45",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Mid-sprint check — 60% of story points complete. Mobile fix and memory leak are behind schedule."},

        # --- Day -6 ---
        {"title": "Daily Standup", "date": d(-6), "start_time": "09:00", "end_time": "09:15",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Daily sync — staging DB ready, Rahul starting memory leak investigation."},
        {"title": "Sprint Planning — Backlog Grooming", "date": d(-6), "start_time": "13:00", "end_time": "13:45",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Groomed backlog for next sprint. Prioritized CI/CD pipeline and monitoring dashboards."},

        # --- Day -5 ---
        {"title": "Daily Standup", "date": d(-5), "start_time": "09:00", "end_time": "09:15",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Daily sync — Meera finished integration tests, Ankit starting mobile fix."},

        # --- Day -4 ---
        {"title": "Daily Standup", "date": d(-4), "start_time": "09:00", "end_time": "09:15",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Daily sync — Rahul found memory leak source (unclosed DB connections). Priya sent revised timeline."},

        # --- Day -3 ---
        {"title": "Client Meeting", "date": d(-3), "start_time": "10:00", "end_time": "11:00",
         "attendees": "Priya, John (client)", "description": "Monthly client check-in. Demoed checkout flow, reviewed timeline. Client accepted 2-week extension. Requested security audit summary before go-live."},
        {"title": "1:1 with Meera", "date": d(-3), "start_time": "14:00", "end_time": "14:30",
         "attendees": "Priya, Meera", "description": "Discussed API documentation progress and Stripe test API key issue."},

        # --- Day -2 ---
        {"title": "Daily Standup", "date": d(-2), "start_time": "09:00", "end_time": "09:15",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Daily sync — Ankit mobile fix 80% done, Meera writing API docs, Rahul deploying memory leak fix."},

        # --- Day -1 (yesterday) ---
        {"title": "Daily Standup", "date": d(-1), "start_time": "09:00", "end_time": "09:15",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Daily sync — Ankit finishing mobile fix, Meera API docs 70% done, Rahul memory leak fix on staging."},
        {"title": "Security Audit Kickoff", "date": d(-1), "start_time": "11:00", "end_time": "12:00",
         "attendees": "Priya, Rahul", "description": "Kicked off security audit of auth flow. Reviewed token storage, session management, CSRF protection scope."},

        # ===== TODAY (day 0) — busy PM day =====
        {"title": "Sprint Planning", "date": d(0), "start_time": "09:30", "end_time": "10:00",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Weekly sprint planning meeting"},
        {"title": "Design Review with Rahul", "date": d(0), "start_time": "11:00", "end_time": "12:00",
         "attendees": "Priya, Rahul", "description": "Review auth module design and PR #342"},
        {"title": "Lunch & Learn — AlloyDB AI Demo", "date": d(0), "start_time": "12:30", "end_time": "13:15",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Internal knowledge sharing — demo of AlloyDB AI semantic search and smart filtering."},
        {"title": "Client Demo Prep", "date": d(0), "start_time": "15:00", "end_time": "15:45",
         "attendees": "Priya, Ankit", "description": "Prepare demo environment and talking points for upcoming client presentation."},
        {"title": "End-of-Day Wrap-Up", "date": d(0), "start_time": "16:30", "end_time": "17:00",
         "attendees": "Priya", "description": "Review today's progress, update task statuses, plan tomorrow's priorities."},

        # ===== TOMORROW (day +1) =====
        {"title": "Weekly Team Standup", "date": d(1), "start_time": "09:00", "end_time": "09:30",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "Daily standup sync"},
        {"title": "1:1 with Meera", "date": d(1), "start_time": "14:00", "end_time": "14:30",
         "attendees": "Priya, Meera", "description": "Discuss backend API progress and blockers"},

        # ===== Day +2 =====
        {"title": "Client Call", "date": d(2), "start_time": "10:00", "end_time": "11:00",
         "attendees": "Priya, John (client)", "description": "Monthly client check-in call — review security audit findings and go-live readiness."},

        # ===== Day +5 =====
        {"title": "Sprint Retrospective", "date": d(5), "start_time": "15:00", "end_time": "16:00",
         "attendees": "Priya, Ankit, Meera, Rahul", "description": "End-of-sprint retro — review what went well, what didn't, and action items for next sprint."},

        # ===== Day +8 =====
        {"title": "Go-Live Readiness Review", "date": d(8), "start_time": "10:00", "end_time": "11:30",
         "attendees": "Priya, John (client), Rahul", "description": "Final go-live readiness review with client. Must happen after security audit is complete."},
    ]

    for evt in seed_events:
        events_ref.add({**evt, "created_at": firestore.SERVER_TIMESTAMP})
    logger.info("Seeded %d demo events.", len(seed_events))


_seed_demo_events()

# ---------------------------------------------------------------------------
# Tool Functions
# ---------------------------------------------------------------------------
def get_current_date() -> dict:
    """Get the current date and time. Call this FIRST whenever the user refers to
    relative dates like 'today', 'tomorrow', 'yesterday', 'this week', 'next Monday', etc.

    Returns:
        Current date in YYYY-MM-DD format, day of week, and current time.
    """
    now = datetime.now()
    result = {
        "status": "success",
        "date": now.strftime("%Y-%m-%d"),
        "day_of_week": now.strftime("%A"),
        "time": now.strftime("%H:%M"),
    }
    logger.info("get_current_date called | result=%s", result)
    return result

def _doc_to_event(doc) -> dict:
    """Convert a Firestore document to a clean event dict (no Sentinel values)."""
    evt = doc.to_dict()
    evt["event_id"] = doc.id
    # Remove or convert created_at — it may be a Sentinel or datetime
    created_at = evt.pop("created_at", None)
    if created_at and not isinstance(created_at, type(firestore.SERVER_TIMESTAMP)):
        evt["created_at"] = str(created_at)
    return evt


def create_event(title: str, date: str, start_time: str, end_time: str,
                 attendees: str = None, description: str = None) -> dict:
    """Create a new calendar event. Automatically checks for conflicts with existing events.

    Args:
        title: Event title (required).
        date: Event date in YYYY-MM-DD format (required).
        start_time: Start time in HH:MM format (required).
        end_time: End time in HH:MM format (required).
        attendees: Comma-separated list of attendee names.
        description: Event description.

    Returns:
        The created event details with its assigned event_id.
        Includes a 'conflicts' list if the new event overlaps with existing events.
    """
    logger.info("create_event called | title=%s date=%s start=%s end=%s attendees=%s",
                title, date, start_time, end_time, attendees)
    try:
        # Check for conflicts with existing events on the same date
        conflicts = []
        for doc in events_ref.where("date", "==", date).stream():
            existing = doc.to_dict()
            ex_start = existing.get("start_time", "")
            ex_end = existing.get("end_time", "")
            # Two events overlap if one starts before the other ends and vice versa
            if start_time < ex_end and end_time > ex_start:
                conflicts.append({
                    "event_id": doc.id,
                    "title": existing.get("title"),
                    "start_time": ex_start,
                    "end_time": ex_end,
                })

        event_data = {
            "title": title,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "attendees": attendees,
            "description": description,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        _, doc_ref = events_ref.add(event_data)
        # Read back the doc to get the resolved timestamp
        created_doc = doc_ref.get()
        result = {"status": "success", "event": _doc_to_event(created_doc)}

        if conflicts:
            result["warning"] = "This event conflicts with existing events!"
            result["conflicts"] = conflicts
            logger.warning("create_event created with conflicts | event_id=%s conflicts=%d",
                           doc_ref.id, len(conflicts))
        else:
            logger.info("create_event success | event_id=%s (no conflicts)", doc_ref.id)

        return result
    except Exception as e:
        logger.error("create_event failed | error=%s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def list_events(date: str = None, start_date: str = None, end_date: str = None) -> dict:
    """List calendar events, optionally filtered by date or date range.

    Args:
        date: Specific date to filter (YYYY-MM-DD). Returns only events on this day.
        start_date: Start of date range (YYYY-MM-DD). Use with end_date.
        end_date: End of date range (YYYY-MM-DD). Use with start_date.

    Returns:
        List of matching events sorted by date and start time.
    """
    logger.info("list_events called | date=%s start_date=%s end_date=%s", date, start_date, end_date)
    try:
        if date:
            query = events_ref.where("date", "==", date)
        elif start_date and end_date:
            query = events_ref.where("date", ">=", start_date).where("date", "<=", end_date)
        else:
            query = events_ref

        results = [_doc_to_event(doc) for doc in query.stream()]
        results.sort(key=lambda e: (e.get("date", ""), e.get("start_time", "")))
        logger.info("list_events success | count=%d", len(results))
        return {"status": "success", "count": len(results), "events": results}
    except Exception as e:
        logger.error("list_events failed | error=%s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def search_events(query: str) -> dict:
    """Search calendar events by text query across titles and descriptions.

    Args:
        query: The text to search for (case-insensitive).

    Returns:
        List of events whose title or description contains the query.
    """
    logger.info("search_events called | query=%s", query)
    try:
        query_lower = query.lower()
        matches = []
        for doc in events_ref.stream():
            evt = doc.to_dict()
            title = (evt.get("title") or "").lower()
            desc = (evt.get("description") or "").lower()
            if query_lower in title or query_lower in desc:
                matches.append(_doc_to_event(doc))

        matches.sort(key=lambda e: (e.get("date", ""), e.get("start_time", "")))
        logger.info("search_events success | query=%s matches=%d", query, len(matches))
        return {"status": "success", "count": len(matches), "events": matches}
    except Exception as e:
        logger.error("search_events failed | error=%s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def find_free_slots(date: str, duration_minutes: int = 30) -> dict:
    """Find free time slots on a given date.

    Args:
        date: Date to check for free slots (YYYY-MM-DD).
        duration_minutes: Minimum duration of free slot in minutes (default: 30).

    Returns:
        List of available time slots on the given date.
    """
    logger.info("find_free_slots called | date=%s duration_minutes=%d", date, duration_minutes)
    try:
        query = events_ref.where("date", "==", date)
        day_events = [doc.to_dict() for doc in query.stream()]
        day_events.sort(key=lambda e: e.get("start_time", ""))

        work_start = "09:00"
        work_end = "17:00"
        free_slots = []
        current = work_start

        for evt in day_events:
            evt_start = evt.get("start_time", "")
            evt_end = evt.get("end_time", "")
            if current < evt_start:
                gap_start = datetime.strptime(current, "%H:%M")
                gap_end = datetime.strptime(evt_start, "%H:%M")
                gap_minutes = (gap_end - gap_start).total_seconds() / 60
                if gap_minutes >= duration_minutes:
                    free_slots.append({
                        "start": current,
                        "end": evt_start,
                        "duration_minutes": int(gap_minutes),
                    })
            current = max(current, evt_end)

        if current < work_end:
            gap_start = datetime.strptime(current, "%H:%M")
            gap_end = datetime.strptime(work_end, "%H:%M")
            gap_minutes = (gap_end - gap_start).total_seconds() / 60
            if gap_minutes >= duration_minutes:
                free_slots.append({
                    "start": current,
                    "end": work_end,
                    "duration_minutes": int(gap_minutes),
                })

        logger.info("find_free_slots success | date=%s slots=%d", date, len(free_slots))
        return {"status": "success", "date": date, "free_slots": free_slots}
    except Exception as e:
        logger.error("find_free_slots failed | error=%s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def update_event(event_id: str, title: str = None, date: str = None,
                 start_time: str = None, end_time: str = None,
                 attendees: str = None, description: str = None) -> dict:
    """Update an existing calendar event. Only provided fields are updated.

    Args:
        event_id: The ID of the event to update (required).
        title: New event title.
        date: New event date in YYYY-MM-DD format.
        start_time: New start time in HH:MM format.
        end_time: New end time in HH:MM format.
        attendees: New comma-separated list of attendee names.
        description: New event description.

    Returns:
        The updated event details or error if event not found.
    """
    logger.info("update_event called | event_id=%s title=%s date=%s start=%s end=%s",
                event_id, title, date, start_time, end_time)
    try:
        doc_ref = events_ref.document(event_id)
        doc = doc_ref.get()
        if not doc.exists:
            logger.warning("update_event not found | event_id=%s", event_id)
            return {"status": "error", "error": f"Event {event_id} not found."}

        updates = {}
        if title is not None:
            updates["title"] = title
        if date is not None:
            updates["date"] = date
        if start_time is not None:
            updates["start_time"] = start_time
        if end_time is not None:
            updates["end_time"] = end_time
        if attendees is not None:
            updates["attendees"] = attendees
        if description is not None:
            updates["description"] = description

        if not updates:
            return {"status": "error", "error": "No fields to update."}

        doc_ref.update(updates)
        updated_doc = doc_ref.get()
        result = {"status": "success", "event": _doc_to_event(updated_doc)}
        logger.info("update_event success | event_id=%s updated_fields=%s", event_id, list(updates.keys()))
        return result
    except Exception as e:
        logger.error("update_event failed | event_id=%s error=%s", event_id, e, exc_info=True)
        return {"status": "error", "error": str(e)}


def delete_event(event_id: str) -> dict:
    """Delete a calendar event by its ID.

    Args:
        event_id: The ID of the event to delete.

    Returns:
        Confirmation of deletion or error if event not found.
    """
    logger.info("delete_event called | event_id=%s", event_id)
    try:
        doc_ref = events_ref.document(event_id)
        doc = doc_ref.get()
        if not doc.exists:
            logger.warning("delete_event not found | event_id=%s", event_id)
            return {"status": "error", "error": f"Event {event_id} not found."}

        deleted = _doc_to_event(doc)
        doc_ref.delete()
        logger.info("delete_event success | event_id=%s title=%s", event_id, deleted.get("title"))
        return {"status": "success", "deleted": deleted}
    except Exception as e:
        logger.error("delete_event failed | event_id=%s error=%s", event_id, e, exc_info=True)
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Agent Definition
# ---------------------------------------------------------------------------

root_agent = LlmAgent(
    model=Gemini(model=model_name, retry_options=RETRY_OPTIONS),
    name="calendar_agent",
    description=(
        "A calendar and scheduling agent backed by Firestore for persistent storage. "
        "Can create, update, delete, list, and search events, and find free time slots. "
        "Events survive restarts and scale-to-zero."
    ),
    instruction="""You are a Calendar & Scheduling assistant. You help users manage their schedule.
Events are stored persistently in Firestore and survive restarts.

**YOUR TOOLS:**
- `get_current_date` — Get today's date and time. You MUST call this FIRST whenever the user
  says "today", "tomorrow", "yesterday", "this week", "next Monday", or any relative date.
  Use the returned date to compute the correct YYYY-MM-DD value before calling other tools.
- `create_event` — Create a new calendar event. **Automatically detects conflicts** with
  existing events on the same date and returns them in the response. Always inform the user
  about conflicts when they are present.
- `list_events` — List events for a specific date or date range.
- `search_events` — Search events by text query across titles and descriptions.
- `find_free_slots` — Find available time slots on a given date (within 09:00–17:00 work hours).
- `update_event` — Update an existing event's fields by event_id (partial updates supported).
- `delete_event` — Remove an event by its event_id.

**CRITICAL RULE — RELATIVE DATES:**
You do NOT know today's date from your training. You MUST call `get_current_date` first
to learn the actual current date before using any other tool when the user mentions
relative dates (today, tomorrow, yesterday, this week, next week, Monday, etc.).
Then compute the correct YYYY-MM-DD from the result.

**HOW TO RESPOND:**
1. For any request with relative dates: call `get_current_date` FIRST, then use the result.
2. When asked about today's schedule: `get_current_date` → `list_events` with that date.
3. When asked to schedule something: `get_current_date` → `find_free_slots` → `create_event`.
4. When asked about this week: `get_current_date` → compute week range → `list_events` with start_date/end_date.
5. When looking for specific events: use `search_events` with a descriptive query.
6. When asked to modify an event: use `update_event` with the event_id and only the fields to change.
7. Present events in chronological order with clear time formatting.
8. **CONFLICTS:** When `create_event` returns a "conflicts" list, you MUST warn the user about
   the overlapping events and suggest alternatives (e.g., a different time slot via `find_free_slots`).
   Never silently ignore conflicts.
""",
    tools=[get_current_date, create_event, list_events, search_events, find_free_slots, update_event, delete_event],
)

app = App(
    name="calendar_agent",
    root_agent=root_agent,
)
