"""Diary-first, request-scoped synthesis helpers.

The FastAPI layer resolves ownership and visible filters before this module is
called.  This module deliberately has no Supabase client and no media access.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from json import dumps
from typing import Any

from pydantic import BaseModel

from app.agent.adapters.langchain_openai import (
    structured_diary_recap_model,
    structured_story_answer_model,
)
from app.agent.schemas import (
    DiaryRecapHighlight,
    DiaryRecapOutput,
    DiaryStoryAnswer,
    MemoryCoverage,
)

log = logging.getLogger(__name__)

_VISIBLE_FILTER_KEYS = {"query", "date_from", "date_to", "mood", "media_type", "entry_ids"}


def synthesize_memory_result(state: dict[str, Any]) -> dict[str, Any]:
    """Produce a structured answer without logging source diary text.

    A concise deterministic answer is returned only when the configured model
    is unavailable.  It keeps the request useful while making no claim to have
    analyzed media or inferred anything beyond the supplied entries.
    """

    try:
        payload = _invoke_structured_memory_model(state)
        return _normalise_model_payload(state, payload)
    except Exception as error:  # External model availability must not expose diary content in logs.
        log.warning(
            "Diary memory synthesis unavailable for run_id=%s (%s); using factual fallback",
            state.get("run_id"),
            type(error).__name__,
        )
        return _deterministic_memory_result(state)


def _invoke_structured_memory_model(state: dict[str, Any]) -> dict[str, Any]:
    entries = state["source_entries"]
    request_context = {
        "trigger": state["trigger"],
        "query": state.get("query"),
        "period": state.get("period"),
        "filters": {
            key: value
            for key, value in (state.get("filters") or {}).items()
            if key in _VISIBLE_FILTER_KEYS and value not in (None, "", [])
        },
        "entries": entries,
    }
    system = (
        "You are DayFora, a private diary memory guide. Answer only from the supplied saved "
        "entry records. Do not infer feelings, health, personality, relationships, or facts not "
        "in those records. Do not claim to have heard audio or seen photos: they are not provided. "
        "Do not paraphrase a user's words as a feeling or emotion, and do not use speculative "
        "phrases such as 'seems', 'appears', or 'feels'. An explicit mood field may be reported "
        "only as a user-selected mood, never as a diagnosis or inferred emotional state. Keep the "
        "answer concise, factual, warm, and source-linked. Never print UUIDs or other source IDs "
        "in prose; return them only in the structured source_entry_ids field. Address the reader "
        "directly as 'you' and 'your'; never refer to 'the user'. A "
        "reflection prompt is optional, one creative but neutral question grounded in the supplied "
        "words, and must not be therapeutic, judgmental, or speculative. Preserve the user's language where "
        "practical."
    )
    user = dumps(request_context, ensure_ascii=False, default=str)

    if state["trigger"] == "ask_diary":
        response = structured_story_answer_model().invoke([("system", system), ("user", user)])
    else:
        recap_system = (
            f"{system} This is an explicit recap for the supplied date period. Do not invent a "
            "recap when the supplied entries do not support it. Write a 3–5 sentence narrative "
            "with a beginning, a meaningful middle transition, and a closing thread; connect "
            "specific details across the supplied dates instead of listing entries. Derive a "
            "specific title from that storyline rather than using a generic title. Make every "
            "supplied entry count exactly once in highlights and source_entry_ids. Keep the date "
            "coverage factual. End with one warm, optional follow-up question such as 'I wonder "
            "what happened next?' only when it follows from the supplied words."
        )
        response = structured_diary_recap_model().invoke([("system", recap_system), ("user", user)])
    return response.model_dump(mode="json") if isinstance(response, BaseModel) else dict(response)


def _normalise_model_payload(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Validate shape locally; graph validation separately enforces source ownership."""

    if state["trigger"] == "ask_diary":
        result = DiaryStoryAnswer.model_validate(payload)
        result.reflection_prompt = "Which cited moment would you like to revisit?"
        return result.model_dump(mode="json")
    result = DiaryRecapOutput.model_validate(payload)
    entries = list(state.get("source_entries") or [])
    entry_ids = [str(entry["id"]) for entry in entries]
    model_highlights = {str(highlight.entry_id): highlight for highlight in result.highlights}
    result.highlights = [
        model_highlights.get(
            entry_id,
            DiaryRecapHighlight(entry_id=entry_id, text=str(entry.get("title") or "Saved entry")),
        )
        for entry_id, entry in ((str(entry["id"]), entry) for entry in entries)
    ]
    result.source_entry_ids = entry_ids
    dates = [date.fromisoformat(str(entry["local_date"])) for entry in entries]
    result.coverage = MemoryCoverage(
        entry_count=len(entries), start_date=min(dates), end_date=max(dates)
    )
    result.reflection_prompt = _follow_up_question(result.reflection_prompt)
    result.title = _address_reader(result.title)
    if result.title.casefold().strip() in {
        "a look back",
        "a week in review",
        "your week in review",
        "weekly recap",
    }:
        result.title = _derive_recap_title(entries)
    result.summary = _address_reader(result.summary)
    result.highlights = [
        highlight.model_copy(update={"text": _address_reader(highlight.text)})
        for highlight in result.highlights
    ]
    return result.model_dump(mode="json")


def _deterministic_memory_result(state: dict[str, Any]) -> dict[str, Any]:
    """A narrow no-model fallback that cites only entries it names."""

    entries = state["source_entries"]
    source_ids = [str(entry["id"]) for entry in entries]
    titles = [str(entry["title"]) for entry in entries]
    coverage = _coverage(entries)
    if state["trigger"] == "recap":
        start = entries[-1]["local_date"]
        end = entries[0]["local_date"]
        ordered_titles = [str(entry["title"]) for entry in reversed(entries)]
        first_title = ordered_titles[0]
        last_title = ordered_titles[-1]
        middle_title = ordered_titles[len(ordered_titles) // 2]
        summary = (
            f"From {start} to {end}, your notes move from ‘{first_title}’ through "
            f"‘{middle_title}’ to ‘{last_title}’. The sequence gives the week a shape without "
            "filling in what you did not write."
        )
        return {
            "title": "Your week in sequence",
            "summary": summary,
            "highlights": [
                {"entry_id": str(entry["id"]), "text": str(entry["title"])} for entry in entries
            ],
            "coverage": coverage,
            "source_entry_ids": source_ids,
            "reflection_prompt": "I wonder what thread from these days you want to follow next?",
        }
    return {
        "answer": "Matching saved moments include " + "; ".join(titles) + ".",
        "coverage": coverage,
        "source_entry_ids": source_ids,
        "reflection_prompt": "Which of these moments would you like to revisit?",
    }


def _coverage(entries: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [date.fromisoformat(str(entry["local_date"])) for entry in entries]
    return {
        "entry_count": len(entries),
        "start_date": min(dates).isoformat(),
        "end_date": max(dates).isoformat(),
    }


def _address_reader(value: str) -> str:
    """Keep recap copy in second person even when the model slips."""

    value = re.sub(r"\bthe user's\b", "your", value, flags=re.IGNORECASE)
    return re.sub(r"\bthe user\b", "you", value, flags=re.IGNORECASE)


def _derive_recap_title(entries: list[dict[str, Any]]) -> str:
    """Create a factual non-generic title if the model returns a placeholder."""

    first = str(entries[-1].get("title") or "Your first note")
    last = str(entries[0].get("title") or "your latest note")
    if first == last:
        return f"A week around {first}"
    return f"From {first} to {last}"


def _follow_up_question(value: str | None) -> str:
    """Keep a recap's optional prompt as a genuine, gentle question."""

    if value and value.strip() and value.strip().endswith("?"):
        return _address_reader(value.strip())
    return "I wonder what happened next?"
