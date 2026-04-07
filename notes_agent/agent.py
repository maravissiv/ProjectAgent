"""Notes Agent — ADK agent using GCS for persistent note storage.

Stores notes as markdown files in a GCS bucket so they survive
Cloud Run instance recycling.
"""

import logging
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

from google.adk.agents import LlmAgent
from google.adk.apps.app import App
from google.adk.models import Gemini
from google.cloud import storage
from google.genai.types import HttpRetryOptions

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# Retry configuration for Gemini model calls
RETRY_OPTIONS = HttpRetryOptions(initial_delay=1, max_delay=3, attempts=30)


# ---------------------------------------------------------------------------
# GCS Configuration
# ---------------------------------------------------------------------------

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
GCS_NOTES_BUCKET = os.getenv("GCS_NOTES_BUCKET", f"{project_id}-bucket")
GCS_NOTES_PREFIX = os.getenv("GCS_NOTES_PREFIX", "notes_hackathon/")
model_name = os.getenv("MODEL", "gemini-2.5-flash")


storage_client = storage.Client(project=project_id)
bucket = storage_client.bucket(GCS_NOTES_BUCKET)

# ---------------------------------------------------------------------------
# Seed Demo Notes (only if bucket prefix is empty)
# ---------------------------------------------------------------------------

def _seed_demo_notes():
    """Seed demo notes for the 'Day in the Life of a PM' scenario.

    Dates are relative to today so the demo works on any day.
    """
    existing = list(bucket.list_blobs(prefix=GCS_NOTES_PREFIX, max_results=1))
    if existing:
        logger.info("GCS prefix '%s' already has data, skipping seed.", GCS_NOTES_PREFIX)
        return

    today = datetime.now().date()
    d = lambda offset: (today + timedelta(days=offset)).strftime("%Y-%m-%d")

    logger.info("Seeding demo notes into GCS bucket '%s'...", GCS_NOTES_BUCKET)

    seed_notes = {
        f"sprint-planning-{d(-13)}.md": f"""# Sprint Planning Notes — {d(-13)}

## Attendees
Priya, Ankit, Meera, Rahul

## Sprint Goals
- Complete checkout frontend rewrite (Ankit)
- Finish backend checkout APIs + Stripe integration (Meera)
- Resolve production memory leak (Rahul)
- Client demo prep and timeline delivery (Priya)

## Key Decisions
- Prioritize mobile responsiveness fix — client demo is coming up
- Rahul to investigate memory leak before taking on new DevOps work
- Meera to pair with Ankit on checkout API contract to avoid integration issues

## Action Items
- [ ] Ankit: Checkout frontend — target completion by {d(5)}
- [ ] Meera: Checkout backend APIs — target completion by {d(5)}
- [ ] Rahul: Memory leak root cause by {d(-4)}
- [ ] Priya: Share revised timeline with client by {d(-5)}
""",

        f"design-review-checkout-{d(-10)}.md": f"""# Design Review — Checkout Wireframes — {d(-10)}

## Attendees
Priya, Ankit, John (client)

## Summary
Reviewed Ankit's high-fidelity wireframes for the checkout page redesign.

## Feedback
- **John (client)**: Loved the new payment form layout. Suggested slightly darker CTA button for accessibility.
- **Priya**: Asked about mobile breakpoint handling — Ankit confirmed responsive grid down to 320px.
- Color palette approved with one tweak: primary CTA from #2196F3 to #1976D2 for better contrast.

## Decisions
- Wireframes approved — Ankit cleared to start implementation
- Mobile-first approach confirmed
- Ankit will use the new React component library (v3)

## Next Steps
- Ankit to begin checkout frontend rewrite by {d(-8)}
- Meera to align backend API contract with wireframe data fields
""",

        f"client-meeting-notes-{d(-3)}.md": f"""# Client Meeting Notes — {d(-3)}

## Attendees
Priya, John (client)

## Agenda
1. Project status update
2. Dashboard demo walkthrough
3. Revised timeline review
4. Q&A and next steps

## Discussion
- John expressed concern about the mobile dashboard issues — asked for ETA on fix
- Demo of current checkout flow went well, client liked the new payment form design
- Client requested a security audit summary before go-live
- Timeline was reviewed — client accepted the 2-week extension for mobile fixes

## Action Items
- [ ] Priya: Send security audit summary to John by {d(3)}
- [ ] Ankit: Fix mobile dashboard issues (HIGH priority)
- [ ] Priya: Schedule follow-up client call for {d(2)}

## Next Meeting
{d(2)} — Monthly client check-in call
""",

        f"standup-{d(-1)}.md": f"""# Standup Notes — {d(-1)}

## Yesterday's Progress
- **Ankit**: Continued work on mobile responsiveness fix for dashboard. Grid layout issues on <768px mostly resolved.
- **Meera**: API documentation for payments endpoint — about 70% done. Writing error code reference.
- **Rahul**: Found the memory leak source — unclosed DB connections in the order service batch processor.

## Today's Plan
- **Ankit**: Finish mobile fix, start on checkout frontend rewrite
- **Meera**: Complete API docs, start on cart validation unit tests
- **Rahul**: Deploy memory leak fix to staging, start CI/CD pipeline setup

## Blockers
- Rahul needs staging access credentials for the payments microservice — Priya to follow up with DevOps
- Meera waiting on Stripe test API keys — Priya to check with finance team
""",

        f"security-audit-scope-{d(-1)}.md": f"""# Security Audit Scope & Preliminary Findings — {d(-1)}

## Audit Lead
Rahul (with Priya oversight)

## Scope
1. **Token Storage** — Review JWT storage mechanism (localStorage vs httpOnly cookies)
2. **Session Management** — Session expiry, rotation, concurrent session handling
3. **CSRF Protection** — Verify CSRF tokens on all state-changing endpoints
4. **Rate Limiting** — Check rate limits on login, password reset, and API endpoints
5. **OAuth2 Integration** — Review PR #342 auth module (Rahul's implementation)

## Preliminary Findings
- Token storage: Currently using localStorage — **RECOMMEND** migrating to httpOnly cookies
- Session expiry: Set to 24h — acceptable for internal use, but client may want shorter for production
- CSRF: Implemented on form submissions but **MISSING** on two API endpoints (cart update, payment initiate)
- Rate limiting: Login endpoint has rate limiting (5 attempts/min), but password reset does not

## Status
In progress — full report due by {d(2)} for client review before go-live.

## Action Items
- [ ] Rahul: Complete auth flow review and document all findings
- [ ] Priya: Compile summary for John (client) by {d(3)}
- [ ] Rahul: Fix CSRF gaps on cart and payment endpoints
""",

        f"previous-sprint-retro-{d(-14)}.md": f"""# Sprint Retrospective — {d(-14)}

## Attendees
Priya, Ankit, Meera, Rahul

## What Went Well
- Staging database provisioning completed ahead of schedule (Rahul)
- Stripe webhook handler shipped with comprehensive test coverage (Meera)
- Good collaboration between Ankit and Meera on API contract alignment

## What Didn't Go Well
- Production memory leak was deprioritized too long — should have investigated earlier
- Client timeline was delayed because we underestimated mobile responsive work
- Terraform drift went undetected for 2 weeks — need better drift detection

## Action Items for Next Sprint
- [ ] Rahul: Set up automated Terraform drift detection alerts
- [ ] Priya: Add buffer time for mobile/responsive work in future estimates
- [ ] Team: Prioritize production bugs over new features going forward
- [ ] Meera: Document API contracts before implementation starts

## Metrics
- Story points planned: 34
- Story points completed: 28 (82%)
- Carryover: 6 points (mobile fix, memory leak)
""",

        "team-roster.md": """# Project Team Roster

## Core Team
| Name | Role | Focus Area |
|------|------|------------|
| **Priya** | Project Manager | Coordination, client comms, timeline |
| **Ankit** | Frontend Developer | React, mobile, checkout UI |
| **Meera** | Backend Developer | APIs, payments, database |
| **Rahul** | DevOps Engineer | CI/CD, monitoring, infrastructure |

## Key Stakeholders
- **John** — Client point of contact

## Communication
- Daily standup: 9:00 AM
- Sprint planning: Mondays 9:30 AM
- Client calls: Bi-weekly
""",
    }

    for filename, content in seed_notes.items():
        blob = bucket.blob(f"{GCS_NOTES_PREFIX}{filename}")
        blob.upload_from_string(content, content_type="text/markdown")
    logger.info("Seeded %d demo notes.", len(seed_notes))


_seed_demo_notes()

# ---------------------------------------------------------------------------
# Tool Functions
# ---------------------------------------------------------------------------

def save_note(filename: str, content: str) -> dict:
    """Save a note as a markdown file in cloud storage.

    Args:
        filename: The filename for the note (e.g. 'sprint-planning-2026-03-30.md').
                  Must end with .md extension.
        content: The markdown content of the note.

    Returns:
        Confirmation with the saved filename.
    """
    logger.info("save_note called | filename=%s content_length=%d", filename, len(content))
    if not filename.endswith(".md"):
        filename = filename + ".md"
    try:
        blob = bucket.blob(f"{GCS_NOTES_PREFIX}{filename}")
        blob.upload_from_string(content, content_type="text/markdown")
        result = {"status": "success", "filename": filename}
        logger.info("save_note success | filename=%s", filename)
        return result
    except Exception as e:
        logger.error("save_note failed | filename=%s error=%s", filename, e, exc_info=True)
        return {"status": "error", "error": str(e)}


def read_note(filename: str) -> dict:
    """Read a note from cloud storage.

    Args:
        filename: The filename of the note to read (e.g. 'sprint-planning-2026-03-30.md').

    Returns:
        The note content or an error if not found.
    """
    logger.info("read_note called | filename=%s", filename)
    try:
        blob = bucket.blob(f"{GCS_NOTES_PREFIX}{filename}")
        if not blob.exists():
            logger.warning("read_note not found | filename=%s", filename)
            return {"status": "error", "error": f"Note '{filename}' not found."}
        content = blob.download_as_text()
        logger.info("read_note success | filename=%s content_length=%d", filename, len(content))
        return {"status": "success", "filename": filename, "content": content}
    except Exception as e:
        logger.error("read_note failed | filename=%s error=%s", filename, e, exc_info=True)
        return {"status": "error", "error": str(e)}


def list_notes() -> dict:
    """List all saved notes in cloud storage.

    Returns:
        List of note filenames sorted by last modified time.
    """
    logger.info("list_notes called")
    try:
        blobs = list(bucket.list_blobs(prefix=GCS_NOTES_PREFIX))
        notes = []
        for b in blobs:
            name = b.name.removeprefix(GCS_NOTES_PREFIX)
            if name:  # skip the prefix-only entry
                notes.append({"filename": name, "updated": str(b.updated)})
        notes.sort(key=lambda n: n["updated"], reverse=True)
        logger.info("list_notes success | count=%d", len(notes))
        return {"status": "success", "count": len(notes), "notes": notes}
    except Exception as e:
        logger.error("list_notes failed | error=%s", e, exc_info=True)
        return {"status": "error", "error": str(e)}


def search_notes(query: str) -> dict:
    """Search through note contents for a query string.

    Args:
        query: The text to search for (case-insensitive).

    Returns:
        List of notes containing the query with matching excerpts.
    """
    logger.info("search_notes called | query=%s", query)
    try:
        blobs = list(bucket.list_blobs(prefix=GCS_NOTES_PREFIX))
        query_lower = query.lower()
        matches = []
        for b in blobs:
            name = b.name.removeprefix(GCS_NOTES_PREFIX)
            if not name:
                continue
            content = b.download_as_text()
            if query_lower in content.lower():
                # Find a short excerpt around the first match
                idx = content.lower().index(query_lower)
                start = max(0, idx - 50)
                end = min(len(content), idx + len(query) + 50)
                excerpt = content[start:end]
                matches.append({"filename": name, "excerpt": f"...{excerpt}..."})
        logger.info("search_notes success | query=%s matches=%d", query, len(matches))
        return {"status": "success", "count": len(matches), "matches": matches}
    except Exception as e:
        logger.error("search_notes failed | query=%s error=%s", query, e, exc_info=True)
        return {"status": "error", "error": str(e)}

# ---------------------------------------------------------------------------
# Agent Definition
# ---------------------------------------------------------------------------

root_agent = LlmAgent(
    model=Gemini(model=model_name, retry_options=RETRY_OPTIONS),
    name="notes_agent",
    description=(
        "A notes and knowledge management agent. Can save meeting notes, "
        "search through existing notes, read note files, and list all saved notes. "
        "Uses Google Cloud Storage for persistent storage."
    ),
    instruction="""You are a Notes & Knowledge assistant. You help users save, find, and manage their notes.

**YOUR TOOLS:**
- `save_note` — Save a note to cloud storage. Always use .md extension and descriptive filenames.
- `read_note` — Read the contents of a specific note file.
- `list_notes` — List all saved notes.
- `search_notes` — Search through note contents for specific text.

**FILE NAMING CONVENTION:**
Use descriptive, kebab-case filenames with dates when relevant:
- Meeting notes: `sprint-planning-2026-03-30.md`
- Client notes: `client-demo-prep-2026-03-30.md`
- General notes: `project-timeline-update.md`

**HOW TO RESPOND:**
1. When saving notes: create well-formatted markdown with headers, bullet points, and action items
2. When searching: use `search_notes` first, then `read_note` for relevant matches
3. When asked about previous notes: `list_notes` first to show what's available
4. Confirm the filename when saving or reading
5. Always format saved notes with a title header, date, and organized content
""",
    tools=[save_note, read_note, list_notes, search_notes],
)

app = App(
    name="notes_agent",
    root_agent=root_agent,
)
