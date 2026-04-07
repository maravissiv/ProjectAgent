# Calendar Agent

ADK agent for schedule management backed by **Firestore** for persistent event storage. Events survive Cloud Run cold starts and scale-to-zero. Exposed via A2A protocol on port 8002.

Comes pre-seeded with demo events for the "Day in the Life of a PM" scenario (on first run if collection is empty).

## Prerequisites

- Python 3.13+
- Google Cloud project with Firestore enabled (Native mode)

## Firestore Setup

1. Go to [Firebase Console](https://console.firebase.google.com) or [Cloud Firestore](https://console.cloud.google.com/firestore)
2. Create a Firestore database in **Native mode**
3. The agent auto-creates the `calendar_events_hackathon` collection on first use

### IAM Permissions

The service account needs `roles/datastore.user` on the project:

```bash
# For Cloud Run service account:
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/datastore.user"
```

**Local development:** Authenticate with `gcloud auth application-default login`.

## Environment Variables

For Vertex AI:
```bash
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=YourProjectNameHere
GOOGLE_CLOUD_LOCATION=DesiredLocationHere
PROJECT_ID=ProjectIDHere
PROJECT_NUMBER=ProjectNumberHere
SA_NAME=proj1-service
SERVICE_ACCOUNT=proj1-service@ProjectIDHere.iam.gserviceaccount.com
MODEL="gemini-2.5-flash"
```

Optional override:
```bash
FIRESTORE_CALENDAR_COLLECTION=calendar_events_hackathon   # default
```

## Local Run

```bash
cd calendar_agent
pip install -r requirements.txt
uvicorn serve:a2a_app --host localhost --port 8002
```

Agent card available at `http://localhost:8002/.well-known/agent.json`.


## Testing

```bash
# Check agent card
curl http://localhost:8002/.well-known/agent.json
```

## Tools

| Tool | Description |
|---|---|
| `create_event` | Create a new calendar event with title, date, time, attendees, description |
| `list_events` | List events for a specific date or date range |
| `search_events` | Search events by text query across titles and descriptions |
| `find_free_slots` | Find available time slots on a given date (09:00–17:00) |
| `update_event` | Update an existing event's fields (partial updates supported) |
| `delete_event` | Delete an event by its event_id |

## Notes

- Events are stored in Firestore (`calendar_events_hackathon` collection) and persist across restarts.
- Demo events are seeded automatically on first run if the collection is empty.
- No OAuth or external API dependencies — uses native Firestore Python SDK.

## Command to deploy

Ensure that the agentcard is updated with the details of the actual URL.
```bash
cd calendar_agent
source .env
adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=europe-west1 \
  --service_name=calendar-agent \
  --with_ui \
  --a2a \
  . \
  -- \
  --service-account=$SERVICE_ACCOUNT 

```
