# DayFora System Architecture

## High-level architecture

```text
Expo mobile app
  ├─ Supabase Auth
  ├─ Private Supabase Storage (original audio/images; short-lived signed URLs)
  ├─ Expo push notifications
  └─ FastAPI backend
       ├─ Product API and authorization
       ├─ LangGraph memory workflows
       ├─ OpenAI API (search/recap synthesis only)
       └─ PostgreSQL-backed LangGraph checkpoints
```

Supabase Postgres is the source of truth for diary, media metadata, recaps, and preferences. LangGraph checkpoints provide workflow recovery only; they are not a second diary database.

## Trust and privacy boundaries

```text
Mobile: authenticated user session; no privileged secrets
  -> FastAPI: validates identity and owns product-data access
       -> Supabase: service role only after ownership verification
       -> OpenAI: backend-only key, receives minimum request-scoped text
       -> Private Storage: never public media URLs
```

- Audio and image blobs are stored under private user paths and never proxied through FastAPI for the MVP.
- V1 private storage is encrypted at rest. This is not end-to-end encryption: a true client-held-key design would prevent a backend agent from reading content.
- The agent never receives raw audio/image media by default. It receives only user-authored title/body, explicit mood, dates, and verified filters needed for an explicitly requested search/recap.
- Mobile talks directly only to Supabase Auth and backend-issued signed storage upload/download URLs. All product-data reads and writes flow through FastAPI.

## Backend responsibilities

FastAPI authenticates callers, validates direct diary writes, issues signed media URLs, reads user-owned diary data, and starts explicitly requested agent workflows. LangGraph performs bounded retrieval and synthesis—not capture processing, transcription, image understanding, draft review, or autonomous daily work. Hybrid retrieval may combine deterministic title/body lexical ranking with an optional Supabase-hosted text embedding index; ownership, approval, and visible filters are applied before semantic candidates are merged.

## API contract

```text
GET    /health
POST   /v1/media/upload-url                 Create a private signed upload URL and media metadata row
POST   /v1/entries                          Create one direct diary entry with media_item_ids
GET    /v1/entries                          List diary entries newest first
GET    /v1/entries/{entry_id}               Read full entry, addenda, and signed media URLs
PATCH  /v1/entries/{entry_id}               Edit today's original entry only
POST   /v1/entries/{entry_id}/addenda       Append reflection/media to a past entry
DELETE /v1/entries/{entry_id}               Permanently delete entry and eligible unshared media
DELETE /v1/media/{media_item_id}            Delete user-owned attachment where lifecycle permits
GET    /v1/explore?date=YYYY-MM-DD          Fetch selected-day diary state and recap availability
GET    /v1/explore/discover                 Browse on-this-day, saved recaps, media/mood/date filters
GET    /v1/explore/search                   Deterministic text/date/mood/media search over saved entries
POST   /v1/explore/ask                      Create temporary, source-linked answer from verified search matches
POST   /v1/recaps                           Generate a weekly/monthly temporary recap for an explicit period
POST   /v1/recaps/{recap_id}/save           Save/bookmark a generated recap
DELETE /v1/recaps/{recap_id}                Delete a saved recap
POST   /v1/device-tokens                    Register/update a push token
PATCH  /v1/notification-preferences         Update diary/weekly reminder settings
```

`POST /v1/entries` validates: an authenticated owner, a non-empty title with no more than 10 words, a local date, and at least one of a non-empty body or an owned audio/image media item. It upserts only the current date’s editable original; it must reject an attempt to overwrite a past original.

The client creates a private media metadata row and signed upload URL, uploads directly to Storage, then includes uploaded `media_item_ids` in the entry or addendum request. Orphaned failed uploads are cleaned up by a safe backend job.

`POST /v1/explore/ask` accepts an explicit query and/or visible filter/entry IDs. The backend resolves and verifies matches before the graph runs. It must not pass a whole diary history to the model because a user typed a broad question.

## Direct-save lifecycle

```text
optional media selected
  -> create media metadata + signed private upload URL
  -> client uploads original blob directly to private Storage
  -> user submits title + content/media references
  -> FastAPI validates and saves diary entry immediately
  -> entry appears in Diary
```

There is no capture table, processing status, draft state, transcript, image description, or review interrupt in v1.

## Agent lifecycle

```text
user requests search question or recap
  -> FastAPI verifies user, request scope, and source entries
  -> LangGraph loads minimum title/body/mood/date source set
  -> model returns structured answer/recap with source IDs
  -> FastAPI validates source IDs and returns temporary result
  -> user may save a recap; source entries remain unchanged
```

## Jobs and notifications

- Send at most one user-selected diary reminder per day and one optional weekly recap notification.
- A recap is generated only after user request/opening its recap flow, not as an opaque scheduled model job. A notification may invite the user to generate/read it.
- Use deterministic idempotency keys for saved-recap and notification jobs.
- Do not rely on in-process FastAPI background tasks for durable production work; use a durable worker/queue when needed beyond the hackathon.

## Deletion and retention

- Deletion is permanent from the user perspective; do not present soft deletion as final deletion.
- Deleting an entry deletes its addenda and unlinks media. Delete a storage object only when no remaining entry/addendum references it.
- Deleting a media attachment removes it from its entry/addendum and private storage after ownership/lifecycle checks.
- Deleting a saved recap removes its payload and related graph checkpoint. Temporary answers are not persisted as product records.
- Operational logs must never include raw diary content. Retain only minimum non-content operational metadata for at most 30 days.

## Deployment target

Deploy one FastAPI service and one Supabase project. Keep mobile and API independently deployable; do not split the hackathon product into microservices.
