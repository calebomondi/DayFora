# DayFora LangGraph Agent Contract

## Purpose

DayFora’s agent is a private, on-demand memory guide. It helps a user search, connect, and recap their own saved diary history. It does not write the diary, process media by default, act as an accountability coach, or behave like an always-on chatbot.

## What the agent can do

1. **Ask your diary:** answer a specific question from verified matching entries, with source cards.
2. **Weekly/monthly recap:** produce a concise, source-linked recap for an explicit date range.
3. **Reflection prompt:** optionally offer one neutral question after a recap, grounded only in its sources.

Examples:

- “What did I say about Build Week?”
- “What happened around my birthday?”
- “Show days I marked as mixed this month.”
- “What have I written about university recently?”

## What the agent must not do

- Create, rewrite, approve, delete, or silently alter a diary entry or addendum.
- Transcribe, describe, classify, or send voice/photo attachments to a model by default.
- Scan the device, camera roll, or run continuously in the background.
- Infer or diagnose emotion, health, personality, relationships, productivity, or protected traits.
- Claim to have seen media it did not receive, invent sources, or make an unsourced claim.
- Search/summarize the whole diary without a request-scoped filter and user-visible result set.

## Invocation events

- User submits `Ask your diary` in Explore.
- User explicitly requests a weekly/monthly recap.
- User saves a recap after reading it (a small persistence action; no new model call necessary).

## Workflows

### Ask your diary

```text
START
  -> validate_request
  -> resolve_query_to_visible_filters
  -> retrieve_verified_matching_entries
  -> synthesize_structured_answer
  -> validate_returned_source_ids
  -> return_temporary_source_linked_answer
  -> END
```

The answer is temporary. It can link to DiaryReader entries but cannot mutate them.

### Recap

```text
START
  -> validate_period_and_user
  -> retrieve_saved_entries_in_period
  -> stop_with_insufficient_material when needed
  -> synthesize_structured_recap
  -> validate_returned_source_ids
  -> return_recap_for_reading_or_optional_save
  -> END
```

## State

Never place binary media, signed URLs, API keys, arbitrary full-history text, or opaque permanent memory in graph state.

```python
from typing import Any, Literal, TypedDict


class DayForaAgentState(TypedDict, total=False):
    run_id: str                       # idempotency key
    user_id: str
    trigger: Literal["ask_diary", "recap"]
    query: str | None
    period: dict[str, str] | None     # visible start/end date
    filters: dict[str, Any]           # text/date/mood/media-presence filters
    source_entries: list[dict[str, Any]]
    # each source contains only id, local_date, title, body, explicit mood
    result: dict[str, Any] | None
    errors: list[str]
```

`source_entries` is a minimum verified set. Media presence may be a filter but media bytes, transcripts, and descriptions are never included.

## Structured output contracts

### Story answer

```json
{
  "answer": "You mentioned the hackathon in three entries between July 14 and July 19. You wrote about finishing the first demo and later refining the diary flow.",
  "coverage": {"entry_count": 3, "start_date": "2026-07-14", "end_date": "2026-07-19"},
  "source_entry_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "reflection_prompt": "What part of that week do you most want to remember?"
}
```

### Recap

```json
{
  "title": "A week of firsts",
  "summary": "You saved four moments this week, including the first working demo and a quieter day of reflection.",
  "highlights": [
    {"entry_id": "uuid-1", "text": "The first demo worked."}
  ],
  "coverage": {"entry_count": 4, "start_date": "2026-07-13", "end_date": "2026-07-19"},
  "reflection_prompt": "Which moment would you like to carry into next week?"
}
```

Rules:

- Return only source IDs from supplied `source_entries`; backend validates them again.
- Preserve the user’s language where possible. Do not translate, normalize, or rewrite source text unless the user explicitly asks for a translation/summarization mode.
- If evidence is insufficient, return a typed `insufficient_material` result rather than inventing a recap.
- Keep answers concise, factual, and source-linked. A reflection prompt is optional, one sentence, and never therapeutic or judgmental.

## Narrow tools

```python
async def resolve_diary_filters(user_id: str, query: str, filters: dict) -> dict: ...
async def get_matching_entries(user_id: str, filters: dict, limit: int) -> list[dict]: ...
async def get_entries_for_period(user_id: str, start_date: str, end_date: str) -> list[dict]: ...
async def save_recap(user_id: str, run_id: str, payload: dict) -> str: ...
async def delete_recap(user_id: str, recap_id: str) -> None: ...
```

Every tool verifies ownership. Model synthesis never owns database writes; FastAPI validates and performs any explicit save.

## Persistence and safety

- Thread IDs: `ask:{user_id}:{run_id}` and `recap:{user_id}:{period_start}:{period_end}:{run_id}`.
- Use a durable PostgreSQL checkpointer in deployed environments.
- Avoid raw diary text in logs. Store operational status and IDs only.
- Save only a recap the user explicitly chooses to keep. Do not retain temporary questions/answers as hidden agent memory.
- An eventual opt-in “make this media searchable” feature is a separate, user-consented product flow requiring explicit policy, review/deletion controls, and schema work; it is not part of v1.
