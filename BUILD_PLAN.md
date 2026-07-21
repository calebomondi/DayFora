# DayFora Build Plan

## Definition of done for the hackathon demo

An authenticated user creates a titled diary entry with a note, voice recording, and/or photo; it saves immediately and privately. They reopen the original media in Diary, search/revisit it in Explore, and ask a source-linked question or read a recap without the agent ever rewriting their diary.

## Product pivot — diary-first v1

The prior activity/draft design is intentionally retired. Preserve existing user data during refactoring; do not blindly delete deployed tables or files. Remove Activities, goals, streaks, check-ins, capture-to-draft processing, transcription/image-description pipelines, and draft-review UI from the active v1 experience.

## Milestone 0 — Foundation

- Expo, FastAPI, Supabase project structure, environment examples, formatting/linting, and `GET /health`.
- Explore placeholder using mock data.

**Acceptance:** Android emulator renders Explore and `/health` succeeds.

## Milestone 1 — Diary-first product shell

- First-time-only onboarding based on `profiles.onboarding_completed_at`.
- Root floating `Diary | Explore` navigation; Explore default.
- Shared root top bar with wordmark, Profile, and Settings.
- Mock direct-entry composer, Diary list/reader, Explore date rail, and unified discovery/search shell.

**Acceptance:** A user can navigate the complete diary-first demo story using mock data with no backend.

## Milestone 2 — Private direct-save foundation

- Supabase Auth, migration/RLS for the simplified diary schema, and private storage.
- Direct entry API with required <=10-word title and body-or-media validation.
- Private signed upload/download URLs for audio/images.
- Edit-today and append-to-past behavior.

**Acceptance:** Two users cannot read each other’s entries, media, addenda, or recaps; a saved entry appears immediately without agent processing.

## Milestone 3 — Diary media experience

- In-app audio recording and user-selected image upload.
- Diary reader with original playback and image gallery.
- Explicit mood/heart selector, date-aware chronological list, addenda, and deletion lifecycle.

**Acceptance:** A user can save/reopen original media and append to yesterday without rewriting the original.

## Milestone 4 — Memory agent

- LangGraph retrieval/recap state, typed tools, durable checkpoints, and strict source validation.
- Explore deterministic filters/search plus `Ask your diary` temporary source-linked answer.
- Weekly/monthly recap generation and optional saving.

**Acceptance:** An agent answer and recap cite only matching user-owned saved entries and cannot modify diary data.

## Milestone 5 — Demo hardening

- Diary and weekly-recap notification preferences.
- Loading/error/retry states, accessibility, privacy labels, deletion checks, and seeded demo story.
- Backup demo recording.

**Acceptance:** Demo is polished, private by default, and robust under an empty diary, failed upload, no search matches, and insufficient recap material.

## Refactor order for an already-built old shell

1. Inventory existing routes, API contracts, migrations, and mock state; identify what is activity/draft-only.
2. Change root types/routes/navigation from Activities to a two-tab `Diary | Explore` shell; fold all existing Memory/discovery routes into Explore.
3. Replace capture-to-draft UI with direct entry composer and immediate optimistic save.
4. Remove active calls/triggers to activity, drafts, processing, transcription, and image-description code. Do not delete legacy DB tables without migration review.
5. Implement simplified API/schema, then connect Explore discovery, retrieval, and recaps.
6. Run tests after each vertical slice.
