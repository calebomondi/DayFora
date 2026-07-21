# DayFora UI/UX Specification

## Design thesis

DayFora feels like a quiet personal place to keep and revisit life—not a productivity dashboard, social feed, task manager, or AI chat app. The user is always the author. AI is a deliberate lens over memories they have already chosen to save.

Follow Apple’s Human Interface Guidelines: clear hierarchy, familiar native controls, content before chrome, Dynamic Type, 44pt touch targets, restrained motion, and platform-appropriate behavior on Android.

## Visual direction: Quiet green

- **Canvas:** warm ivory `#F8F7F0`; dark mode uses near-black green charcoal.
- **Grouped surface:** pale lavender gray `#F1F0F5`; soft elevated dark equivalent in dark mode.
- **Accent:** `#4CAE63`; use once per screen for a primary action, selected tab/segment, or small progress cue.
- **Accent wash:** transparent/pale green such as `rgba(76, 174, 99, 0.18)`, never a solid green date tile.
- **Typography:** platform system font, relaxed diary line height, sentence case, accessible scale.
- **Shape:** continuous 20–24pt grouped surfaces, 16–20pt media surfaces, circular 44pt utility actions. Avoid harsh borders, gradients, stock wellness art, and dense metric cards.
- **Motion:** 180–250ms for sheets and state changes; respect reduced motion. Use light haptics only for meaningful save, recorder, or selection actions.

## Information architecture

```text
Diary                         Explore
chronological                 selected day + rediscovery
entries                       capture + search + recaps
reader/addendum               on this day + Ask your diary
```

`Explore` is the default route after authentication and one-time onboarding. Root navigation is a floating bottom pill with exactly `Diary` and `Explore`; it is navigation only, never a compose button.

## Shared root top bar

Diary and Explore share one fixed header above scrollable content.

```text
DayFora                                              (avatar) (settings)
```

- Left: a quiet textual `DayFora` wordmark, not a page title or marketing lockup.
- Right: separate Profile and Settings actions, each with a 44pt minimum target and clear accessibility label. They may be visually grouped in a subtle transparent capsule but remain independent controls.
- Profile opens account/privacy/export/delete/sign-out options. Settings opens reminders, appearance, permissions, and agent preferences.
- Use warm ivory with no heavy divider. Respect the top safe area; root content scrolls beneath it.
- Do not show a redundant `Diary` or `Explore` heading below it.
- Hide this shared header in onboarding/auth, diary composer, recorder, DiaryReader, search/Ask sheets, recap detail, media viewer, and any other focused child flow. Those screens use native back/close navigation.

## Onboarding

Onboarding appears only for authenticated accounts whose `profiles.onboarding_completed_at` is null. A completed account always opens Explore; closing/reinstalling the app must not repeat onboarding.

1. **Welcome:** “Make room for the days that matter.” Explain private-by-default storage, user ownership, and no camera-roll scanning.
2. **Make it yours:** first name and timezone. Optional intent wording only: remember my days, document a season, keep a personal record.
3. **Choose a moment:** optional diary reminder with native time picker and a clear “Not now.” Ask notification permission only after user taps Set reminder.
4. **First memory:** land on Explore and invite one direct entry. Request microphone/photo permissions only when the corresponding action is tapped.

## Direct entry composer

The composer is a focused sheet/full screen, not a draft-review surface.

```text
New memory                                      Close

Give this day a title *
[ The first demo worked                         ]
  0/10 words

What would you like to keep? (optional)
[ Write a little about it…                      ]

[ Record voice ]  [ Add photos ]

How did today feel? (optional)
  ♥ Happy/fun   ♥ Sad/dull   ♥ Mixed   ♡ Quiet

                                      [ Save memory ]
```

- Title is mandatory, human-written, maximum 10 words. Show a live word count and block save beyond ten.
- Require at least one of non-empty written description, audio, or image. Explain this plainly before save.
- User may combine all three content types.
- Save directly after upload/validation. There is no transcription, AI description, AI draft, processing spinner, or approval step.
- Audio and photos remain original attachments. Do not imply the app/agent understands them.
- The heart is optional explicit user input: red happy/fun, blue sad/dull, orange mixed, quiet is an ivory/outline heart, and no selection remains possible. Never infer a heart from writing/media.

## Explore: today’s gentle home

Explore is a selected-day home, not a dashboard or permanent chat. The shared top bar appears first; the date rail sits directly beneath it.

### Centered date rail

Use a horizontally scrollable five-to-seven-day date rail. On first open, Today is centered and selected.

```text
Thu          Fri        TODAY         Sun          Mon
17 Jul       18 Jul     19 Jul        20 Jul       21 Jul
                         selected
```

- Selected Today is tall/rounded with transparent green wash and dark-green/primary text, never solid `#4CAE63`.
- Unselected days are quiet text, not individual cards.
- Tapping updates all Explore content to that day. Historical dates show only their real saved record/recap; they never show a current-day capture demand.
- A small Today control appears when browsing another date.

### Daily state

| Selected-day state | Content |
| --- | --- |
| Today has no entry | “Today is still yours. A small note now can become a memory later.” → `Capture today` |
| Today has an entry | title, short body excerpt or “Voice note / photos attached,” plus `Open memory` and quiet `Keep reflecting` |
| Historical date has entry | factual historical card only; `Open memory` |
| Historical date is empty | “Nothing was saved for this day.” with no pressure to backfill |

Keep one clear primary action. `Capture today` opens the direct composer. Do not show activity, streak, goal, or draft language.

### Rediscover in Explore

Below the selected-day content, Explore becomes the quiet discovery layer. Show at most one contextual rediscovery card near the top (a weekly recap, an On-this-day memory, or a saved recap) so it never feels like a dashboard.

```text
This week, in brief                                  ›
You saved 4 moments. Read a source-linked recap.

Rediscover
[ Search your diary                               ]

On this day
Jul 20, 2025 · The first demo worked                ›

Browse
[ Photos ] [ Voice notes ] [ Happy days ] [ This month ]

Ask your diary
[ What would you like to revisit?                  ]
```

- Show recap only when enough saved written material exists; otherwise hide it.
- Search opens a dedicated full-screen search with native back/close, visible time/mood/media filters, and matching entry cards. It is the gateway to detailed discovery—not a competing root tab.
- Deterministic search matches user title/body, date/date range, explicit mood, and media presence. It never claims to search within unprocessed media. Natural phrases such as “last Sunday” resolve into a visible date filter before results load.
- Media filters mean entries containing an attachment, not inferred audio/image content. `On this day` finds entries from the same calendar date in earlier years.
- Saved recaps and user bookmarks appear lower in this Explore discovery area. Do not auto-select “best” memories.
- `Ask your diary` opens a focused sheet with prompt suggestions and the visible matching scope, not a persistent chatbot.
- Example prompts: “What did I say about Build Week?”, “What happened last month?”, “Show happy days this week.”
- Answers are temporary and always show source cards. Do not expose an opaque agent “insight” feed.

## Diary: chronological ownership

Diary is the source-of-truth, newest-first list. It is not a recap or duplicate memory browser.

```text
[ if today has no entry ]
Today is still yours.                       [ Capture today ]

[pen] The first demo worked                       Yesterday
I got the capture flow working and finally…
♥ Happy/fun · [speaker] · [image] 2

[pen] A quieter Sunday                            Friday
Voice note attached
♡ Quiet · [speaker]
```

- Place the conditional `Capture today` invitation at the top when today lacks an entry. It complements Explore.
- Card anatomy: pen icon, user title, relative date, max-three-line body excerpt if present, otherwise an honest media-only label, explicit mood if selected, then independent audio/image indicators/counts.
- Never show `AI draft`, `transcribed`, image-description, or provenance badges in v1.
- Relative date: `Today`, `Yesterday`, weekday inside current Sunday–Saturday week, then `Mon, Jul 15` for older entries.
- Tapping a card animates into `DiaryReader`; use Apple Zoom/shared element where supported, short scale/fade fallback elsewhere, and preserve list position on close.

### DiaryReader and addenda

The reader is a scrollable full-screen version of the entry: full title, full written description, explicit mood label, responsive original image gallery, and a playable original-audio row. It has no AI-generated media text.

- Today: user can edit title/body/mood/media.
- Past original: title/body/original media are read-only; show `Add reflection`.
- Add reflection opens a focused composer for text and/or new media. Addenda display after the original under `Added on [date/time]`; a collapsed list card may say `+ 1 reflection`.

## Notifications

Use invitations, never guilt:

| Situation | Copy |
| --- | --- |
| Daily reminder | “A small moment to remember today?” |
| Weekly reminder | “Your week has a story when you’re ready to revisit it.” |
| Recap available | “A quiet look back at your saved week?” |

## Accessibility and platform adaptation

- Support Dynamic Type, screen readers, sufficient contrast, logical focus order, and 44pt targets.
- Icons have accessible labels; color is never the sole signal for mood, media, or selection.
- Respect reduced motion and system appearance.
- Use system sheets, grouped lists, pickers, navigation stacks, and platform-familiar back behavior. Do not imitate iOS chrome at Android usability’s expense.

## Components to build first

1. `RootTopBar` — wordmark plus Profile/Settings actions.
2. `FloatingTabBar` — Diary and Explore.
3. `DiaryComposer` — title validation, body/audio/image input, explicit mood, direct save.
4. `DiaryExcerptCard` — pen, relative date, excerpt/media-only state, mood, attachment indicators.
5. `DiaryReader` — full original content, audio player, image gallery, addenda.
6. `CaptureTodayBanner` — conditional invitation shared by Diary and Explore.
7. `DateRail` — centered transparent-green Today selection.
8. `ExploreDiscovery` — on-this-day, one contextual recap, media/mood/date filters, and saved recaps.
9. `DiarySearch` — visible filters, source results, Ask entry point.
10. `SourceLinkedAnswer` and `RecapCard` — coverage, sources, optional save; no mutation controls.

## UX acceptance criteria

- Completed users land on Explore, which has the shared top bar, centered transparent-green Today rail, and one appropriate direct capture/open action.
- Root navigation is a floating `Diary | Explore` pill and never obscures content.
- Creating an entry requires a <=10-word title and description/audio/image, then saves immediately with no AI draft step.
- Diary is chronological, shows original attachments honestly, and lets users edit only today or append to past entries.
- Explore supports on-this-day, media/mood/time search, source entry opening, saved recaps, and bounded Ask-your-diary answers without duplicating the Diary list.
- The agent does not receive or claim to understand audio/photos by default; every answer/recap is temporary or explicitly saved, source-linked, and cannot edit diary content.
