# Notes Agent

ADK agent that uses Google Cloud Storage for persistent markdown note management. Exposed via A2A protocol on port 8003.

## Prerequisites

- Python 3.13+
- A GCS bucket (defaults to `{GOOGLE_CLOUD_PROJECT}-bucket`)

## GCS Permissions

The service account (or user credentials) running this agent needs the following IAM permissions on the GCS bucket:

| Permission | Required For |
|---|---|
| `storage.objects.create` | `save_note` |
| `storage.objects.get` | `read_note`, `search_notes` |
| `storage.objects.list` | `list_notes`, `search_notes` |

The predefined role **`roles/storage.objectUser`** covers all of these.

**Local development:** Authenticate with `gcloud auth application-default login`.

**Cloud Run:** Assign the role to the Cloud Run service account:
```bash
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:<SERVICE_ACCOUNT_EMAIL>" \
  --role="roles/storage.objectUser" \
  --condition="expression=resource.name.startsWith('projects/_/buckets/${GOOGLE_CLOUD_PROJECT}-bucket/objects/notes_hackathon/'),title=notes-prefix-only"
```

Or without condition scoping (broader access):
```bash
gsutil iam ch serviceAccount:<SERVICE_ACCOUNT_EMAIL>:objectUser gs://${GOOGLE_CLOUD_PROJECT}-bucket
```

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

Optional overrides:
```bash
GCS_NOTES_BUCKET=<your-bucket>       # default: {GOOGLE_CLOUD_PROJECT}-bucket
GCS_NOTES_PREFIX=notes_hackathon/              # default: notes_hackathon/
```

## Local Run

```bash
cd notes_agent
pip install -r requirements.txt
uvicorn serve:a2a_app --host localhost --port 8003
```

Agent card available at `http://localhost:8003/.well-known/agent.json`.


## Testing

```bash
# Check agent card
curl http://localhost:8003/.well-known/agent.json
```

## Tools

| Tool | Description |
|---|---|
| `save_note` | Save a markdown note to GCS (`notes_hackathon/` prefix) |
| `read_note` | Read a specific note by filename |
| `list_notes` | List all saved notes sorted by last modified |
| `search_notes` | Search note contents for a query string |

## Notes

- Notes are stored in GCS at `gs://{bucket}/notes_hackathon/` and persist across Cloud Run instance restarts.
- File naming convention: kebab-case with dates (e.g., `sprint-planning-2026-03-30.md`).
- No Node.js or MCP server dependencies — uses direct GCS Python SDK.

## Deployment 

Ensure agent card is updated with the correct URL.

```bash
cd notes_agent
source .env
adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=europe-west1 \
  --service_name=notes-agent \
  --with_ui \
  --a2a \
  . \
  -- \
  --service-account=$SERVICE_ACCOUNT
```  