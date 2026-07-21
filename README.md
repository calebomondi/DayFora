# DayFora

Private, diary-first memory keeping for students and builders. Save a titled note, voice recording, photo, or combination directly; use a source-linked AI agent later to rediscover the story you saved.

## Stack

- Mobile: Expo, React Native, TypeScript
- Backend: Python, FastAPI, LangGraph
- Data/auth/media: Supabase Postgres, Auth, private Storage
- AI: OpenAI API through the backend only

## Product shape

```text
Diary       Save and read chronological original entries
Explore     Today, search, on-this-day, filters, recaps, and Ask your diary
```

Read root docs before implementing, in this order:

1. `PRODUCT.md`
2. `ARCHITECTURE.md`
3. `AGENT.md`
4. `DATA_MODEL.md`
5. `BUILD_PLAN.md`
6. `UI_UX.md`
7. `AGENTS.md`

## Local development

The repository may be edited from WSL, but Android Studio, Android Emulator, Expo, Node, and frontend dependencies run on Windows. Use Windows PowerShell for mobile commands. See `AGENTS.md`.
