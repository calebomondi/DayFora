# DayFora — Engineering Guidance

Read this file and every root-level `*.md` project document before planning or changing code. If documents conflict, `PRODUCT.md` defines product intent and this file defines engineering constraints. Flag a real conflict instead of silently choosing.

## Product in one sentence

DayFora is a private, diary-first memory app that lets people save titled written, audio, and photo moments directly, then use a source-linked AI agent to rediscover and reflect on their own history.

## Repository shape

```text
mobile/       Expo + React Native + TypeScript application
backend/      Python + FastAPI + LangGraph API/worker
supabase/     SQL migrations, Row-Level Security policies, seed data
```

## Non-negotiable product rules

- A diary entry is a date-based personal record. A user has at most one original entry per local calendar day; today may be edited and a past entry accepts timestamped addenda only.
- An entry requires a human-written title of at most 10 words and at least one of: written description, original voice note, or user-selected image. Save it directly; there is no AI entry draft, approval state, or AI-authored diary body in v1.
- Audio and images are original private attachments. Do not transcribe, describe, scan, index, or send them to an AI model by default.
- The user-selected mood/heart is explicit user input, never an AI inference.
- The agent may use only user-owned, approved/saved entry title, written description, explicit mood, date, and user-chosen filters by default. It returns source-linked, temporary search answers and recaps; it never edits, creates, deletes, or diagnoses entries.
- There are no activities, streaks, goals, check-ins, or accountability features in v1.
- All user media and diary data is private by default. No social feed, sharing, public URLs, camera-roll scanning, background media collection, video understanding, or autonomous agent behavior.

## Technical constraints

- Mobile: Expo React Native and TypeScript.
- Backend: FastAPI, Python, LangGraph, PostgreSQL/Supabase.
- Use Supabase Auth, Postgres, private Storage, and Row-Level Security.
- OpenAI credentials and Supabase service-role credentials are backend secrets only; never expose them in the mobile app.
- Store audio/image blobs in private object storage, never in Postgres. Store only private paths and metadata in the database. Private storage encryption at rest is not end-to-end encryption; do not claim E2EE unless client-held keys are actually implemented.
- LangGraph state contains IDs, user-authored text selected for the request, filters, and structured responses only—never media blobs, public URLs, or the whole diary by default.
- Use structured outputs for model responses. LangGraph side effects must be idempotent with a request/run key.

## Design constraints

- DayFora’s action color is `#4CAE63`. Follow `UI_UX.md`: Apple HIG-inspired, warm, grouped-list, low-chrome; no generic dashboard cards or gradients.
- Root navigation is a floating pill with `Diary` and `Explore`. `Explore` is the default signed-in destination; the tab bar is navigation only.
- The two root tabs share a fixed warm-ivory top bar: `DayFora` wordmark left, separate Profile and Settings actions right. Hide it in onboarding and focused child flows.
- Onboarding is shown only when `profiles.onboarding_completed_at` is null. Completed users land on Explore.
- Explore has no redundant page title or full-date heading. Its date rail is the date context and selected Today uses a transparent `#4CAE63` wash, never solid green.
- Diary is a newest-first chronological source-of-truth list. Each card shows the user title, a clamped written description if present, the explicit mood if chosen, and independent audio/image indicators. Never show an `AI draft` badge.
- Explore combines selected-day capture with search, recaps, on-this-day discovery, media/mood filters, and saved recaps. Keep it curated, not dashboard-like.

## Local development on Windows + WSL

- The repository is stored on Windows and may be edited by Codex from WSL.
- Android Studio, Android Emulator, Expo, Node, and frontend `node_modules` run on Windows.
- Do not run `npm install`, Expo, or Android build commands in WSL for `mobile/`.
- Backend may run with Windows Python for the simplest emulator networking setup.
- When giving mobile commands, provide Windows PowerShell commands.

## Working style

- Inspect existing files before editing. Work in small vertical slices and preserve user data during the pivot.
- Keep API payloads typed/validated with Pydantic and TypeScript. Add/update tests for non-trivial backend behavior.
- Run relevant lint, typecheck, and tests after changes; report exact results.
- Do not add dependencies, services, or authentication flows without explaining why.
