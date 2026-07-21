# DayFora Data Model

Supabase/Postgres is the product source of truth. Every user-owned row includes `user_id` and Row-Level Security limits access to `auth.uid()`.

## Tables

### profiles

```text
id (uuid, PK; matches auth.users.id)
display_name (text, nullable)
timezone (text, required)
onboarding_completed_at (timestamptz, nullable)
created_at
updated_at
```

`onboarding_completed_at` is the account-level routing source of truth: null routes an authenticated user to onboarding; non-null routes them to Explore.

### diary_entries

```text
id (uuid, PK)
user_id (uuid, FK profiles.id)
local_date (date)
title (text, required; maximum 10 words enforced by API and database constraint/trigger)
body (text, nullable)
mood (happy_fun | sad_dull | mixed | quiet, nullable)
created_at
updated_at

UNIQUE (user_id, local_date)
```

An original entry requires a non-empty title plus either non-empty `body` or at least one attached media item. It is directly saved user content: no `draft`, `approved`, or AI-processing status exists.

### media_items

```text
id (uuid, PK)
user_id (uuid, FK profiles.id)
storage_path (text, private bucket path; never a public URL)
media_type (audio | image)
captured_at (timestamptz, nullable)
upload_source (in_app | user_selected)
upload_status (pending | uploaded | failed | deleted)
created_at
```

Do not store transcripts, image descriptions, or media-derived AI fields in v1. The optional hybrid retrieval migration stores embeddings only for user-written title/body text, never for audio or images, and keeps those vectors user-owned and rebuildable.

### entry_media

```text
entry_id (uuid, FK diary_entries.id)
media_item_id (uuid, FK media_items.id)
PRIMARY KEY (entry_id, media_item_id)
```

### diary_entry_addenda

Past diary originals are preserved. Addenda are timestamped user-authored reflections or media additions.

```text
id (uuid, PK)
entry_id (uuid, FK diary_entries.id)
user_id (uuid, FK profiles.id)
body (text, nullable)
created_at
```

An addendum requires non-empty body or at least one attached media item.

### addendum_media

```text
addendum_id (uuid, FK diary_entry_addenda.id)
media_item_id (uuid, FK media_items.id)
PRIMARY KEY (addendum_id, media_item_id)
```

### recaps

Only recaps the user explicitly saves belong in this table. A temporary agent answer/recap is not stored here.

```text
id (uuid, PK)
user_id (uuid, FK profiles.id)
recap_type (weekly | monthly | custom)
period_start_date (date)
period_end_date (date)
payload (jsonb; structured title, summary, highlights, coverage, source IDs)
created_at
updated_at

UNIQUE (user_id, recap_type, period_start_date, period_end_date)
```

### saved_memories

Optional user bookmarks; this is user curation, not inferred AI importance.

```text
id (uuid, PK)
user_id (uuid, FK profiles.id)
entry_id (uuid, FK diary_entries.id, nullable)
recap_id (uuid, FK recaps.id, nullable)
created_at
```

Require exactly one of `entry_id` or `recap_id`.

### device_tokens

```text
id (uuid, PK)
user_id (uuid, FK profiles.id)
expo_push_token (unique)
platform (android | ios)
last_seen_at
revoked_at (timestamptz, nullable)
```

### notification_preferences

```text
user_id (uuid, PK, FK profiles.id)
timezone (text)
diary_enabled (boolean)
diary_reminder_time (time, nullable)
weekly_recap_enabled (boolean)
weekly_recap_day (smallint, nullable; ISO day 1–7)
weekly_recap_time (time, nullable)
```

## Relationships

```text
profile 1--* diary_entries
profile 1--* media_items
profile 1--* recaps
profile 1--* saved_memories
diary_entry *--* media_items through entry_media
diary_entry 1--* diary_entry_addenda
diary_entry_addenda *--* media_items through addendum_media
```

## Access control

- Users can select/modify only rows where `user_id = auth.uid()`.
- Storage objects live only under `users/{user_id}/...`; signed URLs are short-lived and user-specific.
- Backend service-role operations verify authenticated ownership before any read/write/signing action.
- No public select policy exists for diary, media, recap, bookmark, or notification data.

## Diary lifecycle

1. User may upload media privately before submitting an entry.
2. `POST /entries` validates title, content requirement, ownership, and `(user_id, local_date)` uniqueness.
3. For today, the original entry may be created or edited; media associations are updated transactionally.
4. For an earlier date with an existing original, reject overwriting and require an addendum.
5. An entry reader displays original body/media first, then addenda in creation order.

## Deletion lifecycle

- Deleting an entry deletes its addenda, entry-media links, bookmarks, and removes saved recap highlights that reference it or marks those highlights unavailable.
- Delete a media object only when it is no longer referenced by any entry/addendum.
- Deleting a recap deletes its saved-memory bookmark and agent checkpoint metadata.
- Never log raw entry body or media content as part of deletion processing.

## Migration note for the v1 pivot

Existing activity, activity-checkin, draft, capture, transcript, AI-description, and insight tables are outside the v1 model. Do not silently drop a deployed user-data table. Add an explicit migration plan: stop new writes first, remove routes/UI, export or retain legacy rows during the hackathon, and only drop data with a reviewed migration after confirming the environment contains no data that must be preserved.
