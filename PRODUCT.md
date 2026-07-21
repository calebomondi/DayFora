# DayFora Product Specification

## Vision

People abandon diaries because capturing a real moment can feel like work. DayFora is a private place to save the day in the form that feels natural—one short title, an optional note, a voice recording, photos, or a combination—then return to it later with help from a careful memory agent.

**Product statement:** DayFora is a private AI memory diary that helps people preserve moments in their own words and rediscover the story they chose to save.

## Initial users

- Students who want to remember ordinary days, school life, travel, friendships, and personal turning points.
- Builders who want a private record of the human side of making something, without turning their diary into a task tracker.

## Core concepts

| Concept | Definition | Primary question |
| --- | --- | --- |
| Diary entry | One user-authored original record for a local calendar day. | “What do I want to remember?” |
| Addendum | A timestamped reflection or attachment added to a past entry without rewriting its original. | “What do I want to add now?” |
| Media | An original voice note or user-selected image attached privately to an entry or addendum. | “What evidence belongs with this memory?” |
| Memory | A way of rediscovering entries through time, search, explicit mood, attached media, or a source-linked recap. | “What do I want to revisit?” |
| Agent response | A temporary, source-linked answer or recap based on user-authorized saved text and filters. | “What does my saved history show?” |

## The magic moment

Someone gives a memory a small title—“The first demo worked”—adds a photo and a short voice note, and saves it immediately. Later, they ask, “What did I say about the hackathon?” DayFora surfaces the matching entries and a concise answer, with every claim linked back to their own records.

## MVP scope

### Included

- Account onboarding, privacy information, diary reminder, and notification preferences.
- Direct diary creation: required title of at most 10 words plus at least one of written description, voice note, or image.
- In-app voice recording and user-selected image attachment, stored in private storage.
- Edit today’s original entry; append timestamped text/media reflections to older entries.
- Optional explicit heart: happy/fun, sad/dull, mixed, quiet, or no selection.
- Diary list and full-screen reader with original playable audio and images.
- Explore as the selected-day home and unified discovery layer: weekly recap, search, on-this-day, media/mood browsing, saved recaps, and deliberate “Ask your diary.”
- A LangGraph agent for source-linked diary search and recaps based on user-authorized text/date/mood context.
- One gentle daily diary reminder and an optional weekly recap reminder.

### Explicitly out of scope for MVP

- Activities, goals, streaks, tasks, check-ins, accountability coaching, or activity reminders.
- AI-written diary entries, AI draft approval, automatic transcription, automatic image descriptions, and automatic media indexing.
- Background camera-roll scanning, media syncing, video understanding, or full video transcription.
- Social sharing, followers, comparisons, public profiles, medical/mental-health analysis, personality analysis, or autonomous agent changes.
- End-to-end encryption claims or implementation. V1 uses private storage and encryption at rest; a backend agent sees only the text explicitly selected for a request.

## Primary flows

### Save a diary entry

1. From Explore or Diary, the user chooses `Capture today`.
2. They enter a required title (maximum 10 words) and add a written description, voice note, image, or any combination. At least one content type is required.
3. The app uploads selected media using private signed URLs and creates the diary entry directly.
4. The user returns to the saved entry—no transcription, AI rewrite, processing state, or review step.
5. Today’s entry remains editable. For prior days, `Add reflection` creates a timestamped addendum.

### Rediscover a memory

1. The user opens Explore and searches, browses a date/media/mood filter, or opens `On this day`.
2. Search returns matching saved entries, never an invisible whole-diary query.
3. The user may ask a bounded question such as “What did I say about Build Week?”
4. The agent answers only from verified matches and displays source entry cards. The answer is temporary unless the user saves it as a recap.

### Generate a recap

1. The user opens a weekly/monthly recap prompt in Explore.
2. The backend resolves the eligible date range and user-owned saved text records.
3. The agent produces a concise structured recap with source IDs and coverage information.
4. The user reads it, opens sources, and optionally saves/bookmarks it. It never changes diary content.

## UX principles

- Calm, warm, private, and unmistakably user-authored.
- Saving is immediate; AI is not a gatekeeper to documenting life.
- A short user-written title is the dependable anchor for every memory, regardless of language or media quality.
- Original media remains original. Do not pretend AI understood audio or images when it did not process them.
- The agent is useful on request, factual, concise, multilingual where model capability permits, and always source-linked.
- Explicit user mood is an optional personal lens, never a diagnosis or inferred label.
- Root account navigation is predictable: wordmark left, Profile and Settings actions right.

## Confirmed MVP decisions

- `title` is required, human-authored, and limited to 10 words. Entry content has no required language and is preserved exactly as entered.
- A new entry must contain at least one of `body`, audio attachment, or image attachment. Titles alone cannot create an entry.
- Audio/images are private attachments. V1 does not create transcripts, image descriptions, media embeddings, or AI provenance from them. With explicit hybrid retrieval enabled, only user-written title/body text may receive a private search embedding.
- The agent may read title/body/mood/date only after the user initiates a specific search or recap. It does not keep hidden memory, run continuously, or receive the entire diary by default.
- Search and agent answers include saved entries only. Recaps and answers are source-linked and cannot edit or create diary entries.
- Diary remains one original entry per local date. Today can be edited; past originals are preserved through append-only addenda.
- Weekly/monthly recaps are optional AI summaries. They are clearly labeled, can be discarded or saved, and do not require approval to affect source records because they never mutate them.
- The backend owns product-data reads/writes. Mobile uses Supabase directly only for authentication and backend-issued private storage URLs.
- Users can permanently delete an entry, addendum, recap, or media item. Associated private objects and agent checkpoints are queued for deletion.

## Success criteria for the hackathon demo

1. A user saves a titled diary entry with a note, voice recording, and/or image without waiting for AI.
2. The entry appears immediately in Diary and opens into a polished reader where original media can be viewed or played.
3. The user finds a past memory through Explore.
4. They ask a bounded question about their diary and receive a concise, source-linked answer.
5. They view a weekly recap whose claims link back to their saved entries.
