from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from hashlib import md5
from json import dumps
from queue import Queue
from threading import Thread
from typing import Any, Callable, Iterator
from uuid import uuid4
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from langgraph.types import Command
from postgrest.exceptions import APIError
from starlette.responses import RedirectResponse, StreamingResponse
from supabase import Client, create_client
from supabase_auth.errors import AuthApiError

from app.activity_consistency import is_eligible_day, refresh_activity_consistency
from app.agent.adapters.langchain_openai import (
    structured_activity_recap_model,
    structured_search_recap_model,
)
from app.agent.graph import build_graph, build_memory_graph, close_checkpointer
from app.agent.memory import synthesize_memory_result
from app.agent.retrieval import hybrid_entry_score, rank_hybrid_entries
from app.agent.streak import calculate_streak
from app.agent.tools.supabase import SupabaseTools
from app.reminders import dispatch_due_reminders
from app.schemas import (
    ActivityCreate,
    ActivityEventResponse,
    ActivityRecapResponse,
    ActivityRecapReview,
    ActivityResponse,
    ActivitySearchResult,
    ActivityStatusUpdate,
    AddendumCreate,
    AddendumResponse,
    AddendumUpdate,
    AgentInsightResponse,
    AskDiaryRequest,
    AskDiaryResponse,
    AttachmentRemovalResponse,
    CaptureCreate,
    CaptureResponse,
    CheckinCreate,
    CheckinResponse,
    DeviceTokenCreate,
    DiaryEntryResponse,
    DiaryEntryUpsert,
    DiaryEntryWrite,
    DiaryMediaPreview,
    DiarySearchFilters,
    DraftResponse,
    DraftReview,
    EntryMediaResponse,
    ExploreAskRequest,
    ExploreAskResponse,
    ExploreContinuityResponse,
    ExploreDiscoveryResponse,
    ExploreFocusResponse,
    ExploreMediaItem,
    ExploreResponse,
    ExploreSourceCard,
    HealthResponse,
    MediaUploadRequest,
    MediaUploadResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    ProfileResponse,
    RecapRequest,
    RecapResponse,
    ReviewResponse,
    SearchRecapHighlightResponse,
    SearchRecapRequest,
    SearchRecapResponse,
    SourceCard,
    TodayResponse,
    UploadUrlRequest,
    UploadUrlResponse,
    WeeklyRecapResponse,
)

load_dotenv()

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_checkpointer()


app = FastAPI(title="DayFora API", version="0.3.0", lifespan=lifespan)


def configured_client(key_name: str) -> Client:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv(key_name, "")
    if not url or not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase is not configured"
        )
    return create_client(url, key)


@lru_cache
def service_client() -> Client:
    return configured_client("SUPABASE_SERVICE_ROLE_KEY")


@lru_cache
def anon_client() -> Client:
    return configured_client("SUPABASE_ANON_KEY")


def optional_response_data(response: Any) -> Any | None:
    """Supabase may return ``None`` for an empty ``maybe_single`` query."""
    return response.data if response is not None else None


def current_user_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        response = anon_client().auth.get_user(authorization.removeprefix("Bearer "))
    except AuthApiError as error:
        # A deleted user can retain a locally cached access token until the app clears it.
        # Never expose the upstream Auth response or turn an authentication failure into a 500.
        log.info("Rejected Supabase bearer token: status=%s code=%s", error.status, error.code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token",
        ) from error

    if response.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
    return str(response.user.id)


def local_today(user_id: str) -> date:
    profile = (
        service_client()
        .table("profiles")
        .select("timezone")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    timezone = profile.get("timezone", "UTC") if profile else "UTC"
    return datetime.now(ZoneInfo(timezone)).date()


def user_timezone(user_id: str) -> str:
    profile = (
        service_client()
        .table("profiles")
        .select("timezone")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    return profile.get("timezone", "UTC") if profile else "UTC"


# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/v1/profile", response_model=ProfileResponse)
async def get_profile(user_id: str = Depends(current_user_id)) -> ProfileResponse:
    profile = (
        service_client()
        .table("profiles")
        .select("onboarding_completed_at, created_at")
        .eq("id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileResponse(**profile)


@app.post("/v1/profile/onboarding-complete", response_model=ProfileResponse)
async def complete_onboarding(user_id: str = Depends(current_user_id)) -> ProfileResponse:
    profile = (
        service_client()
        .table("profiles")
        .update({"onboarding_completed_at": datetime.now(UTC).isoformat()})
        .eq("id", user_id)
        .execute()
        .data
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileResponse(**profile[0])


def activity_is_due_for_date(activity: dict[str, Any], selected_date: date) -> bool:
    return is_eligible_day(activity, selected_date)


def activity_response(row: dict[str, Any], recap_status: str | None = None) -> ActivityResponse:
    current = int(row.get("current_streak") or row.get("streak") or 0)
    return ActivityResponse(
        **{
            **row,
            "streak": current,
            "current_streak": current,
            "longest_streak": int(row.get("longest_streak") or 0),
            "recap_status": recap_status,
        }
    )


def entry_source_badge(payload: dict[str, Any] | None) -> str:
    """Collapse detailed draft provenance into the one entry-level source badge."""
    labels = (payload or {}).get("source_labels") or []
    return "user_written" if "user_written" in labels else "ai_generated"


def enrich_diary_entries(
    entries: list[dict[str, Any]], client: Client, user_id: str
) -> list[DiaryEntryResponse]:
    """Add list-safe provenance and attachment counts to owned diary entries."""
    if not entries:
        return []

    entry_ids = [str(entry["id"]) for entry in entries]
    draft_rows = (
        client.table("drafts")
        .select("entry_id, payload")
        .eq("user_id", user_id)
        .in_("entry_id", entry_ids)
        .eq("status", "approved")
        .execute()
        .data
        or []
    )
    source_by_entry = {
        str(draft["entry_id"]): entry_source_badge(draft.get("payload"))
        for draft in draft_rows
        if draft.get("entry_id")
    }

    media_links = (
        client.table("entry_media")
        .select("entry_id, media_item_id")
        .in_("entry_id", entry_ids)
        .execute()
        .data
        or []
    )
    media_ids = [str(link["media_item_id"]) for link in media_links if link.get("media_item_id")]
    media_rows = (
        client.table("media_items")
        .select("id, media_type")
        .eq("user_id", user_id)
        .in_("id", media_ids)
        .execute()
        .data
        or []
        if media_ids
        else []
    )
    media_type_by_id = {str(media["id"]): media.get("media_type") for media in media_rows}
    counts_by_entry: dict[str, dict[str, int]] = {}
    for link in media_links:
        entry_id = str(link.get("entry_id", ""))
        media_type = media_type_by_id.get(str(link.get("media_item_id", "")))
        if media_type not in {"audio", "image"}:
            continue
        counts = counts_by_entry.setdefault(entry_id, {"audio": 0, "image": 0})
        counts[media_type] += 1

    addenda_rows = (
        client.table("diary_entry_addenda")
        .select("entry_id")
        .eq("user_id", user_id)
        .in_("entry_id", entry_ids)
        .execute()
        .data
        or []
    )
    addenda_counts: dict[str, int] = {}
    for addendum in addenda_rows:
        addendum_entry_id = str(addendum.get("entry_id", ""))
        if addendum_entry_id:
            addenda_counts[addendum_entry_id] = addenda_counts.get(addendum_entry_id, 0) + 1

    return [
        DiaryEntryResponse(
            **{
                **entry,
                "source_badge": source_by_entry.get(str(entry["id"]), "user_written"),
                "audio_count": counts_by_entry.get(str(entry["id"]), {}).get("audio", 0),
                "image_count": counts_by_entry.get(str(entry["id"]), {}).get("image", 0),
                "addenda_count": addenda_counts.get(str(entry["id"]), 0),
            }
        )
        for entry in entries
    ]


def present_v1_entries(
    entries: list[dict[str, Any]], client: Client, user_id: str
) -> list[DiaryEntryResponse]:
    """Present saved diary entries without reading legacy draft/provenance data."""
    if not entries:
        return []
    entry_ids = [str(entry["id"]) for entry in entries]
    links = (
        client.table("entry_media")
        .select("entry_id, media_item_id")
        .in_("entry_id", entry_ids)
        .execute()
        .data
        or []
    )
    media_ids = [str(link["media_item_id"]) for link in links if link.get("media_item_id")]
    media_rows = (
        client.table("media_items")
        .select("id, media_type, storage_path, created_at")
        .eq("user_id", user_id)
        .in_("id", media_ids)
        .execute()
        .data
        or []
        if media_ids
        else []
    )
    media_by_id = {str(row["id"]): row for row in media_rows}
    counts: dict[str, dict[str, int]] = {}
    media_by_entry: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        entry_id = str(link.get("entry_id", ""))
        media = media_by_id.get(str(link.get("media_item_id", "")))
        media_type = media.get("media_type") if media else None
        if media_type in {"audio", "image"}:
            counts.setdefault(entry_id, {"audio": 0, "image": 0})[media_type] += 1
            media_by_entry.setdefault(entry_id, []).append(media)
    addenda_rows = (
        client.table("diary_entry_addenda")
        .select("entry_id")
        .eq("user_id", user_id)
        .in_("entry_id", entry_ids)
        .execute()
        .data
        or []
    )
    addenda: dict[str, int] = {}
    for row in addenda_rows:
        entry_id = str(row.get("entry_id", ""))
        if entry_id:
            addenda[entry_id] = addenda.get(entry_id, 0) + 1

    def preview_for(media: dict[str, Any]) -> DiaryMediaPreview | None:
        storage_path = media.get("storage_path")
        if not storage_path:
            return None
        try:
            signed = client.storage.from_("dayfora-media").create_signed_url(storage_path, 900)
            signed_url = signed.get("signedURL") or signed.get("signedUrl")
        except Exception:  # A list should still load if one preview cannot be signed.
            log.warning("Unable to sign diary list media preview %s", media.get("id"))
            return None
        if not signed_url:
            return None
        return DiaryMediaPreview(
            id=media["id"], media_type=media["media_type"], signed_url=signed_url
        )

    result: list[DiaryEntryResponse] = []
    for entry in entries:
        entry_media = sorted(
            media_by_entry.get(str(entry["id"]), []),
            key=lambda media: str(media.get("created_at") or ""),
            reverse=True,
        )
        image_previews = [
            preview
            for media in entry_media
            if media.get("media_type") == "image"
            for preview in [preview_for(media)]
            if preview is not None
        ][:3]
        audio_preview = next(
            (
                preview
                for media in entry_media
                if media.get("media_type") == "audio"
                for preview in [preview_for(media)]
                if preview is not None
            ),
            None,
        )
        result.append(
            DiaryEntryResponse(
                **{
                    **entry,
                    "mood": entry.get("mood_v1") or entry.get("mood"),
                    "source_badge": "user_written",
                    "audio_count": counts.get(str(entry["id"]), {}).get("audio", 0),
                    "image_count": counts.get(str(entry["id"]), {}).get("image", 0),
                    "addenda_count": addenda.get(str(entry["id"]), 0),
                    "preview_images": image_previews,
                    "preview_audio": audio_preview,
                }
            )
        )
    return result


def signed_media_response(media: dict[str, Any], client: Client) -> EntryMediaResponse:
    signed = client.storage.from_("dayfora-media").create_signed_url(media["storage_path"], 900)
    signed_url = signed.get("signedURL") or signed.get("signedUrl")
    if not signed_url:
        log.error("Storage did not return a signed URL for media %s", media.get("id"))
        raise HTTPException(status_code=502, detail="Unable to prepare private media")
    return EntryMediaResponse(
        id=media["id"],
        media_type=media["media_type"],
        signed_url=signed_url,
        transcript=media.get("transcript"),
        ai_description=media.get("ai_description"),
    )


@app.get("/v1/today", response_model=TodayResponse)
async def get_today(
    local_date: date | None = Query(default=None), user_id: str = Depends(current_user_id)
) -> TodayResponse:
    current_date = local_today(user_id)
    selected_date = local_date or current_date
    if selected_date > current_date:
        raise HTTPException(status_code=422, detail="A future day cannot be explored yet")
    client = service_client()
    entry_result = (
        client.table("diary_entries")
        .select("*")
        .eq("user_id", user_id)
        .eq("local_date", selected_date.isoformat())
        .maybe_single()
        .execute()
    )
    activity_result = (
        client.table("activities")
        .select("*")
        .eq("user_id", user_id)
        .in_("status", ["active", "paused"])
        .order("created_at")
        .execute()
    )
    activities_raw = activity_result.data or []
    tools = SupabaseTools(service_client())
    activities = []
    for row in activities_raw:
        checkins = tools.get_activity_checkins(row["id"], user_id)
        activity_today = datetime.now(ZoneInfo(row.get("timezone", "UTC"))).date()
        streak = calculate_streak(checkins, row, activity_today)
        completed_for_date = any(
            checkin.get("status") == "approved"
            and checkin.get("local_date") == selected_date.isoformat()
            for checkin in checkins
        )
        activities.append(
            ActivityResponse(
                **{
                    **row,
                    "streak": streak,
                    "completed_for_date": completed_for_date,
                    "due_for_date": activity_is_due_for_date(row, selected_date)
                    and not completed_for_date,
                }
            )
        )
    entries = [entry_result.data] if entry_result and entry_result.data else []
    enriched_entries = enrich_diary_entries(entries, client, user_id)
    return TodayResponse(
        local_date=selected_date,
        entry=enriched_entries[0] if enriched_entries else None,
        activities=activities,
    )


def _active_insight(client: Client, user_id: str) -> AgentInsightResponse | None:
    """Return one inspectable insight only when every referenced record is approved and owned."""
    try:
        rows = (
            client.table("agent_insights")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
    except APIError:
        # Keep Explore usable during a rolling deployment where the API arrives
        # before this optional, user-visible table has been migrated.
        log.warning("Agent insights are unavailable until their migration is applied")
        return None
    if not rows:
        return None
    row = rows[0]
    refs = row.get("source_refs") or {}
    entry_ids = [str(value) for value in refs.get("entry_ids", [])]
    checkin_ids = [str(value) for value in refs.get("checkin_ids", [])]
    if len(entry_ids) + len(checkin_ids) < 3:
        return None
    entries = (
        client.table("diary_entries")
        .select("id, local_date")
        .eq("user_id", user_id)
        .eq("status", "approved")
        .in_("id", entry_ids)
        .execute()
        .data
        or []
        if entry_ids
        else []
    )
    checkins = (
        client.table("activity_checkins")
        .select("id, local_date")
        .eq("user_id", user_id)
        .eq("status", "approved")
        .in_("id", checkin_ids)
        .execute()
        .data
        or []
        if checkin_ids
        else []
    )
    if len(entries) != len(set(entry_ids)) or len(checkins) != len(set(checkin_ids)):
        return None
    dates = [date.fromisoformat(str(item["local_date"])) for item in [*entries, *checkins]]
    return AgentInsightResponse(
        id=row["id"],
        insight_type=row["insight_type"],
        body=row["body"],
        source_count=len(dates),
        date_from=min(dates),
        date_to=max(dates),
    )


def _focus_for_today(
    client: Client, activities: list[dict[str, Any]], user_id: str, selected_date: date
) -> tuple[ExploreFocusResponse | None, ExploreContinuityResponse | None]:
    candidates: list[tuple[int, str, dict[str, Any], dict[str, Any] | None, str]] = []
    for activity in activities:
        if not activity_is_due_for_date(activity, selected_date):
            continue
        today_checkin_result = (
            client.table("activity_checkins")
            .select("id")
            .eq("activity_id", activity["id"])
            .eq("user_id", user_id)
            .eq("local_date", selected_date.isoformat())
            .eq("status", "approved")
            .maybe_single()
            .execute()
        )
        today_checkin = optional_response_data(today_checkin_result)
        if today_checkin:
            continue
        latest_result = (
            client.table("activity_checkins")
            .select("id, local_date, next_small_step")
            .eq("activity_id", activity["id"])
            .eq("user_id", user_id)
            .eq("status", "approved")
            .lt("local_date", selected_date.isoformat())
            .order("local_date", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        latest = optional_response_data(latest_result)
        reset_result = (
            client.table("activity_events")
            .select("local_date")
            .eq("activity_id", activity["id"])
            .eq("user_id", user_id)
            .eq("event_type", "streak_reset")
            .gte("local_date", (selected_date - timedelta(days=7)).isoformat())
            .lte("local_date", selected_date.isoformat())
            .limit(1)
            .maybe_single()
            .execute()
        )
        reset = optional_response_data(reset_result)
        next_step = (latest or {}).get("next_small_step")
        if isinstance(next_step, str) and next_step.strip():
            candidates.append(
                (
                    0,
                    "smallest_next_step",
                    activity,
                    latest,
                    "It is due today, and you set this next step yesterday.",
                )
            )
        elif activity.get("end_date") and date.fromisoformat(
            str(activity["end_date"])
        ) <= selected_date + timedelta(days=3):
            candidates.append(
                (
                    1,
                    "nearing_end_date",
                    activity,
                    latest,
                    "It is due today, and its end date is near.",
                )
            )
        elif reset:
            candidates.append(
                (
                    2,
                    "recent_reset",
                    activity,
                    latest,
                    "It is due today after a recent neutral rhythm reset.",
                )
            )
        else:
            candidates.append(
                (
                    3,
                    "recent_activity",
                    activity,
                    latest,
                    "It is due today and is your most recently active due commitment.",
                )
            )
    if not candidates:
        return None, None
    _, rule, activity, latest, reason = choose_focus_candidate(candidates)
    focus = ExploreFocusResponse(activity=activity_response(activity), rule=rule, reason=reason)
    continuity = None
    if (
        latest
        and isinstance(latest.get("next_small_step"), str)
        and latest["next_small_step"].strip()
    ):
        continuity = ExploreContinuityResponse(
            activity_id=activity["id"],
            activity_title=activity["title"],
            checkin_id=latest["id"],
            local_date=latest["local_date"],
            next_small_step=latest["next_small_step"].strip(),
        )
    return focus, continuity


def choose_focus_candidate(
    candidates: list[tuple[int, str, dict[str, Any], dict[str, Any] | None, str]],
) -> tuple[int, str, dict[str, Any], dict[str, Any] | None, str]:
    """Apply the documented focus priority while preserving newest-first ties."""
    return min(candidates, key=lambda item: item[0])


def is_current_explore_date(selected_date: date, current_date: date) -> bool:
    """Historical Explore is recap-only; it must never expose today's prompts."""
    return selected_date == current_date


@app.get("/v1/explore", response_model=ExploreResponse)
async def get_explore(
    selected_date: date | None = Query(default=None, alias="date"),
    user_id: str = Depends(current_user_id),
) -> ExploreResponse:
    current_date = local_today(user_id)
    selected_date = selected_date or current_date
    if selected_date > current_date:
        raise HTTPException(status_code=422, detail="A future day cannot be explored yet")
    client = service_client()
    entry_result = (
        client.table("diary_entries")
        .select("id, user_id, local_date, title, body, mood_v1, created_at, updated_at, status")
        .eq("user_id", user_id)
        .eq("local_date", selected_date.isoformat())
        .eq("status", "approved")
        .maybe_single()
        .execute()
    )
    entry_row = optional_response_data(entry_result)
    entry = None
    if entry_row:
        entry = present_v1_entries(
            [{**entry_row, "mood": entry_row.get("mood_v1")}], client, user_id
        )[0]
    week_start = selected_date - timedelta(days=selected_date.weekday())
    eligible_count = (
        client.table("diary_entries")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("status", "approved")
        .gte("local_date", week_start.isoformat())
        .lte("local_date", selected_date.isoformat())
        .execute()
        .count
        or 0
    )
    return ExploreResponse(
        selected_date=selected_date,
        is_today=selected_date == current_date,
        entry=entry,
        recap_available=eligible_count >= 2,
    )


@app.post("/v1/agent-insights/{insight_id}/dismiss")
async def dismiss_agent_insight(
    insight_id: str, user_id: str = Depends(current_user_id)
) -> dict[str, str]:
    result = (
        service_client()
        .table("agent_insights")
        .update({"status": "dismissed"})
        .eq("id", insight_id)
        .eq("user_id", user_id)
        .eq("status", "active")
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Active insight not found")
    return {"status": "dismissed"}


@app.post("/v1/legacy/explore/ask", response_model=ExploreAskResponse, include_in_schema=False)
async def ask_about_story(
    payload: ExploreAskRequest, user_id: str = Depends(current_user_id)
) -> ExploreAskResponse:
    client = service_client()
    if payload.activity_id:
        owned = (
            client.table("activities")
            .select("id")
            .eq("id", str(payload.activity_id))
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
            .data
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Activity not found")
    entries_query = (
        client.table("diary_entries")
        .select("id, local_date, title, body")
        .eq("user_id", user_id)
        .eq("status", "approved")
    )
    if payload.date_from:
        entries_query = entries_query.gte("local_date", payload.date_from.isoformat())
    if payload.date_to:
        entries_query = entries_query.lte("local_date", payload.date_to.isoformat())
    if payload.query and payload.query.strip():
        term = payload.query.strip()
        entries_query = entries_query.or_(f"title.ilike.%{term}%,body.ilike.%{term}%")
    entries = entries_query.order("local_date", desc=True).limit(20).execute().data or []
    checkins_query = (
        client.table("activity_checkins")
        .select("id, activity_id, local_date, milestone, note")
        .eq("user_id", user_id)
        .eq("status", "approved")
    )
    if payload.activity_id:
        checkins_query = checkins_query.eq("activity_id", str(payload.activity_id))
    if payload.date_from:
        checkins_query = checkins_query.gte("local_date", payload.date_from.isoformat())
    if payload.date_to:
        checkins_query = checkins_query.lte("local_date", payload.date_to.isoformat())
    if payload.query and payload.query.strip():
        term = payload.query.strip()
        checkins_query = checkins_query.or_(f"milestone.ilike.%{term}%,note.ilike.%{term}%")
    checkins = checkins_query.order("local_date", desc=True).limit(20).execute().data or []
    # A named commitment is a valid, explicit activity filter even if the words
    # do not occur in the milestone itself.  Fetch only matching owned activities
    # and their approved records; do not widen this into a diary-wide search.
    if payload.query and payload.query.strip() and not payload.activity_id:
        term = payload.query.strip()
        related_activities = (
            client.table("activities")
            .select("id")
            .eq("user_id", user_id)
            .or_(f"title.ilike.%{term}%,purpose.ilike.%{term}%")
            .limit(8)
            .execute()
            .data
            or []
        )
        related_ids = [str(activity["id"]) for activity in related_activities]
        if related_ids:
            related_query = (
                client.table("activity_checkins")
                .select("id, activity_id, local_date, milestone, note")
                .eq("user_id", user_id)
                .eq("status", "approved")
                .in_("activity_id", related_ids)
            )
            if payload.date_from:
                related_query = related_query.gte("local_date", payload.date_from.isoformat())
            if payload.date_to:
                related_query = related_query.lte("local_date", payload.date_to.isoformat())
            related_checkins = (
                related_query.order("local_date", desc=True).limit(20).execute().data or []
            )
            seen_checkin_ids = {str(checkin["id"]) for checkin in checkins}
            checkins.extend(
                checkin
                for checkin in related_checkins
                if str(checkin["id"]) not in seen_checkin_ids
            )
            linked_entry_ids = {
                str(row["entry_id"])
                for row in client.table("activity_checkins")
                .select("entry_id")
                .eq("user_id", user_id)
                .eq("status", "approved")
                .in_("activity_id", related_ids)
                .execute()
                .data
                or []
                if row.get("entry_id")
            }
            if linked_entry_ids:
                linked_entries_query = (
                    client.table("diary_entries")
                    .select("id, local_date, title, body")
                    .eq("user_id", user_id)
                    .eq("status", "approved")
                    .in_("id", list(linked_entry_ids))
                )
                if payload.date_from:
                    linked_entries_query = linked_entries_query.gte(
                        "local_date", payload.date_from.isoformat()
                    )
                if payload.date_to:
                    linked_entries_query = linked_entries_query.lte(
                        "local_date", payload.date_to.isoformat()
                    )
                linked_entries = (
                    linked_entries_query.order("local_date", desc=True).limit(20).execute().data
                    or []
                )
                seen_entry_ids = {str(entry["id"]) for entry in entries}
                entries.extend(
                    entry for entry in linked_entries if str(entry["id"]) not in seen_entry_ids
                )
    if payload.activity_id:
        linked_ids = {
            str(row.get("entry_id"))
            for row in client.table("activity_checkins")
            .select("entry_id")
            .eq("activity_id", str(payload.activity_id))
            .eq("user_id", user_id)
            .eq("status", "approved")
            .execute()
            .data
            or []
            if row.get("entry_id")
        }
        entries = [entry for entry in entries if str(entry["id"]) in linked_ids]
    if payload.media_type:
        entry_ids = [str(entry["id"]) for entry in entries]
        checkin_ids = [str(checkin["id"]) for checkin in checkins]
        matching_entry_ids = set()
        matching_checkin_ids = set()
        if entry_ids:
            entry_links = (
                client.table("entry_media")
                .select("entry_id, media_item_id")
                .in_("entry_id", entry_ids)
                .execute()
                .data
                or []
            )
            entry_media_ids = [str(row["media_item_id"]) for row in entry_links]
            matching_media_ids = (
                {
                    str(row["id"])
                    for row in client.table("media_items")
                    .select("id")
                    .eq("user_id", user_id)
                    .eq("media_type", payload.media_type)
                    .in_("id", entry_media_ids)
                    .execute()
                    .data
                    or []
                }
                if entry_media_ids
                else set()
            )
            matching_entry_ids = {
                str(row["entry_id"])
                for row in entry_links
                if str(row["media_item_id"]) in matching_media_ids
            }
        if checkin_ids:
            checkin_links = (
                client.table("checkin_media")
                .select("checkin_id, media_item_id")
                .in_("checkin_id", checkin_ids)
                .execute()
                .data
                or []
            )
            checkin_media_ids = [str(row["media_item_id"]) for row in checkin_links]
            matching_media_ids = (
                {
                    str(row["id"])
                    for row in client.table("media_items")
                    .select("id")
                    .eq("user_id", user_id)
                    .eq("media_type", payload.media_type)
                    .in_("id", checkin_media_ids)
                    .execute()
                    .data
                    or []
                }
                if checkin_media_ids
                else set()
            )
            matching_checkin_ids = {
                str(row["checkin_id"])
                for row in checkin_links
                if str(row["media_item_id"]) in matching_media_ids
            }
        entries = [entry for entry in entries if str(entry["id"]) in matching_entry_ids]
        checkins = [checkin for checkin in checkins if str(checkin["id"]) in matching_checkin_ids]
    sources = [
        ExploreSourceCard(
            source_type="diary_entry",
            source_id=item["id"],
            local_date=item["local_date"],
            title=item["title"] or "Diary entry",
            excerpt=item["body"][:180],
        )
        for item in entries
    ] + [
        ExploreSourceCard(
            source_type="activity_checkin",
            source_id=item["id"],
            activity_id=item["activity_id"],
            local_date=item["local_date"],
            title=item["milestone"],
            excerpt=item.get("note"),
        )
        for item in checkins
    ]
    sources.sort(key=lambda item: item.local_date, reverse=True)
    if not sources:
        raise HTTPException(status_code=404, detail="No approved records match those filters")
    dates = [source.local_date for source in sources]
    diary_count = sum(source.source_type == "diary_entry" for source in sources)
    checkin_count = len(sources) - diary_count
    start_label = min(dates).strftime("%b %d").replace(" 0", " ")
    end_label = max(dates).strftime("%b %d").replace(" 0", " ")
    answer = f"Across {len(sources)} approved records from {start_label} to {end_label}, you kept {diary_count} diary moment{'s' if diary_count != 1 else ''} and {checkin_count} activity update{'s' if checkin_count != 1 else ''}."
    return ExploreAskResponse(
        answer=answer,
        source_count=len(sources),
        date_from=min(dates),
        date_to=max(dates),
        sources=sources,
    )


@app.get("/v1/entries", response_model=list[DiaryEntryResponse])
async def list_diary_entries(
    limit: int = Query(default=50, ge=1, le=100),
    before: date | None = None,
    user_id: str = Depends(current_user_id),
) -> list[DiaryEntryResponse]:
    """Return one bounded, newest-first page of the user's approved diary history."""
    query = (
        service_client()
        .table("diary_entries")
        .select(
            "id, user_id, local_date, title, body, mood, mood_v1, day_feeling, status, created_at, updated_at"
        )
        .eq("user_id", user_id)
        .eq("status", "approved")
    )
    if before:
        query = query.lt("local_date", before.isoformat())
    result = query.order("local_date", desc=True).limit(limit).execute()
    rows = [{**row, "mood": row.get("mood_v1") or row.get("mood")} for row in result.data or []]
    return present_v1_entries(rows, service_client(), user_id)


@app.get("/v1/entries/{entry_id}/media", response_model=list[EntryMediaResponse])
async def list_entry_media(
    entry_id: str, user_id: str = Depends(current_user_id)
) -> list[EntryMediaResponse]:
    """Return private media for an owned entry using temporary download URLs."""
    client = service_client()
    entry = (
        client.table("diary_entries")
        .select("id")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .eq("status", "approved")
        .maybe_single()
        .execute()
        .data
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Diary entry not found")

    links = (
        client.table("entry_media").select("media_item_id").eq("entry_id", entry_id).execute().data
        or []
    )
    media_ids = [str(link["media_item_id"]) for link in links if link.get("media_item_id")]
    if not media_ids:
        return []

    media_rows = (
        client.table("media_items")
        .select("id, media_type, storage_path")
        .eq("user_id", user_id)
        .in_("id", media_ids)
        .execute()
        .data
        or []
    )
    media_by_id = {str(media["id"]): media for media in media_rows if media.get("id")}
    response: list[EntryMediaResponse] = []
    for media_id in media_ids:
        media = media_by_id.get(media_id)
        if not media or media.get("media_type") not in {"audio", "image"}:
            continue
        signed = client.storage.from_("dayfora-media").create_signed_url(media["storage_path"], 900)
        signed_url = signed.get("signedURL") or signed.get("signedUrl")
        if not signed_url:
            log.error("Storage did not return a signed URL for media %s", media_id)
            raise HTTPException(status_code=502, detail="Unable to prepare private media")
        response.append(
            EntryMediaResponse(
                id=media["id"],
                media_type=media["media_type"],
                signed_url=signed_url,
                transcript=None,
                ai_description=None,
            )
        )
    return response


@app.get("/v1/entries/{entry_id}/addenda", response_model=list[AddendumResponse])
async def list_entry_addenda(
    entry_id: str, user_id: str = Depends(current_user_id)
) -> list[AddendumResponse]:
    client = service_client()
    entry = (
        client.table("diary_entries")
        .select("id")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .eq("status", "approved")
        .maybe_single()
        .execute()
        .data
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Diary entry not found")
    addenda = (
        client.table("diary_entry_addenda")
        .select("id, entry_id, body, created_at")
        .eq("entry_id", entry_id)
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
        .data
        or []
    )
    if not addenda:
        return []
    addendum_ids = [str(addendum["id"]) for addendum in addenda]
    media_links = (
        client.table("addendum_media")
        .select("addendum_id, media_item_id")
        .in_("addendum_id", addendum_ids)
        .execute()
        .data
        or []
    )
    media_ids = [str(link["media_item_id"]) for link in media_links if link.get("media_item_id")]
    media_rows = (
        client.table("media_items")
        .select("id, media_type, storage_path, transcript, ai_description")
        .eq("user_id", user_id)
        .in_("id", media_ids)
        .execute()
        .data
        or []
        if media_ids
        else []
    )
    media_by_id = {str(media["id"]): media for media in media_rows if media.get("id")}
    media_by_addendum: dict[str, list[EntryMediaResponse]] = {}
    for link in media_links:
        media = media_by_id.get(str(link.get("media_item_id", "")))
        if media and media.get("media_type") in {"audio", "image"}:
            media_by_addendum.setdefault(str(link["addendum_id"]), []).append(
                signed_media_response(media, client)
            )
    return [
        AddendumResponse(
            **addendum,
            media=media_by_addendum.get(str(addendum["id"]), []),
        )
        for addendum in addenda
    ]


@app.post(
    "/v1/entries/{entry_id}/addenda",
    response_model=AddendumResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_entry_addendum(
    entry_id: str, payload: AddendumCreate, user_id: str = Depends(current_user_id)
) -> AddendumResponse:
    client = service_client()
    entry = (
        client.table("diary_entries")
        .select("id, local_date")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .eq("status", "approved")
        .maybe_single()
        .execute()
        .data
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Diary entry not found")
    entry_date = date.fromisoformat(str(entry["local_date"]))
    if entry_date >= local_today(user_id):
        raise HTTPException(
            status_code=409, detail="Use today's edit flow for the current diary entry"
        )
    body = payload.body.strip() if payload.body else None
    created = (
        client.table("diary_entry_addenda")
        .insert({"entry_id": entry_id, "user_id": user_id, "body": body})
        .execute()
        .data[0]
    )
    return AddendumResponse(**created)


@app.post("/v1/addenda/{addendum_id}/upload-url", response_model=UploadUrlResponse)
async def create_addendum_upload_url(
    addendum_id: str, payload: UploadUrlRequest, user_id: str = Depends(current_user_id)
) -> UploadUrlResponse:
    client = service_client()
    addendum = (
        client.table("diary_entry_addenda")
        .select("id")
        .eq("id", addendum_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not addendum:
        raise HTTPException(status_code=404, detail="Reflection not found")
    extension = payload.file_extension.lower().lstrip(".")
    if not extension.isalnum() or len(extension) > 8:
        raise HTTPException(status_code=422, detail="Invalid file extension")
    path = f"users/{user_id}/addenda/{addendum_id}/{uuid4()}.{extension}"
    media = (
        client.table("media_items")
        .insert(
            {
                "user_id": user_id,
                "storage_path": path,
                "media_type": payload.media_type,
                "upload_source": "in_app" if payload.media_type == "audio" else "user_selected",
            }
        )
        .execute()
        .data[0]
    )
    client.table("addendum_media").insert(
        {"addendum_id": addendum_id, "media_item_id": media["id"]}
    ).execute()
    signed = client.storage.from_("dayfora-media").create_signed_upload_url(path)
    return UploadUrlResponse(
        media_item_id=media["id"],
        storage_path=path,
        signed_url=signed["signedUrl"],
        token=signed["token"],
    )


def _remove_unshared_private_media(client: Client, user_id: str, media: dict[str, Any]) -> None:
    """Delete a private object only after its last entry/addendum link is gone."""
    media_id = str(media["id"])
    entry_links = (
        client.table("entry_media").select("entry_id").eq("media_item_id", media_id).execute().data
        or []
    )
    addendum_links = (
        client.table("addendum_media")
        .select("addendum_id")
        .eq("media_item_id", media_id)
        .execute()
        .data
        or []
    )
    if entry_links or addendum_links:
        return
    client.storage.from_("dayfora-media").remove([media["storage_path"]])
    client.table("media_items").delete().eq("id", media_id).eq("user_id", user_id).execute()


def has_saved_entry_content(body: str | None, attachment_count: int) -> bool:
    """A diary record must retain written content or at least one original attachment."""
    return bool((body or "").strip()) or attachment_count > 0


@app.delete("/v1/entries/{entry_id}/media/{media_id}", response_model=DiaryEntryResponse)
async def delete_today_entry_media(
    entry_id: str, media_id: str, user_id: str = Depends(current_user_id)
) -> DiaryEntryResponse:
    """Allow attachment removal only while the original entry is still today's entry."""
    client = service_client()
    entry = optional_response_data(
        client.table("diary_entries")
        .select("id, user_id, local_date, title, body, mood_v1, status, created_at, updated_at")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Diary entry not found")
    if date.fromisoformat(str(entry["local_date"])) != local_today(user_id):
        raise HTTPException(
            status_code=409, detail="Original attachments are preserved after the day has passed"
        )
    links = (
        client.table("entry_media").select("media_item_id").eq("entry_id", entry_id).execute().data
        or []
    )
    if media_id not in {str(link.get("media_item_id", "")) for link in links}:
        raise HTTPException(status_code=404, detail="Attachment not found on this diary entry")
    if not has_saved_entry_content(entry.get("body"), len(links) - 1):
        raise HTTPException(
            status_code=409,
            detail="Keep a written description or another attachment before removing this one",
        )
    media = optional_response_data(
        client.table("media_items")
        .select("id, storage_path")
        .eq("id", media_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not media:
        raise HTTPException(status_code=404, detail="Attachment not found")
    client.table("entry_media").delete().eq("entry_id", entry_id).eq(
        "media_item_id", media_id
    ).execute()
    _remove_unshared_private_media(client, user_id, media)
    return present_v1_entries([entry], client, user_id)[0]


@app.delete("/v1/addenda/{addendum_id}/media/{media_id}", response_model=AttachmentRemovalResponse)
async def delete_addendum_media(
    addendum_id: str, media_id: str, user_id: str = Depends(current_user_id)
) -> AttachmentRemovalResponse:
    """Remove only a user-owned attachment appended in this specific reflection."""
    client = service_client()
    addendum = optional_response_data(
        client.table("diary_entry_addenda")
        .select("id, body")
        .eq("id", addendum_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not addendum:
        raise HTTPException(status_code=404, detail="Reflection not found")
    links = (
        client.table("addendum_media")
        .select("media_item_id")
        .eq("addendum_id", addendum_id)
        .execute()
        .data
        or []
    )
    if media_id not in {str(link.get("media_item_id", "")) for link in links}:
        raise HTTPException(status_code=404, detail="Attachment not found on this reflection")
    media = optional_response_data(
        client.table("media_items")
        .select("id, storage_path")
        .eq("id", media_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not media:
        raise HTTPException(status_code=404, detail="Attachment not found")
    client.table("addendum_media").delete().eq("addendum_id", addendum_id).eq(
        "media_item_id", media_id
    ).execute()
    _remove_unshared_private_media(client, user_id, media)
    addendum_deleted = not has_saved_entry_content(addendum.get("body"), len(links) - 1)
    if addendum_deleted:
        client.table("diary_entry_addenda").delete().eq("id", addendum_id).eq(
            "user_id", user_id
        ).execute()
    return AttachmentRemovalResponse(addendum_deleted=addendum_deleted)


@app.patch("/v1/addenda/{addendum_id}", response_model=AttachmentRemovalResponse)
async def remove_addendum_text(
    addendum_id: str, payload: AddendumUpdate, user_id: str = Depends(current_user_id)
) -> AttachmentRemovalResponse:
    """Clear only appended text; original diary bodies are never addressed by this route."""
    if (payload.body or "").strip():
        raise HTTPException(status_code=422, detail="This route only removes reflection text")
    client = service_client()
    addendum = optional_response_data(
        client.table("diary_entry_addenda")
        .select("id")
        .eq("id", addendum_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not addendum:
        raise HTTPException(status_code=404, detail="Reflection not found")
    links = (
        client.table("addendum_media")
        .select("media_item_id")
        .eq("addendum_id", addendum_id)
        .execute()
        .data
        or []
    )
    if links:
        client.table("diary_entry_addenda").update({"body": None}).eq("id", addendum_id).eq(
            "user_id", user_id
        ).execute()
        return AttachmentRemovalResponse()
    client.table("diary_entry_addenda").delete().eq("id", addendum_id).eq(
        "user_id", user_id
    ).execute()
    return AttachmentRemovalResponse(addendum_deleted=True)


@app.get("/v1/diary/search", response_model=list[DiaryEntryResponse])
async def search_diary_entries(
    query: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    media_type: str | None = Query(default=None, pattern="^(audio|image)$"),
    activity_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    user_id: str = Depends(current_user_id),
) -> list[DiaryEntryResponse]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    client = service_client()
    entries_query = (
        client.table("diary_entries")
        .select("id, user_id, local_date, title, body, mood, day_feeling, status")
        .eq("user_id", user_id)
        .eq("status", "approved")
    )
    if date_from:
        entries_query = entries_query.gte("local_date", date_from.isoformat())
    if date_to:
        entries_query = entries_query.lte("local_date", date_to.isoformat())
    entries = entries_query.order("local_date", desc=True).limit(limit).execute().data or []

    normalized_query = (query or "").strip().casefold()
    if normalized_query:
        entries = [
            entry
            for entry in entries
            if normalized_query in f"{entry.get('title', '')}\n{entry.get('body', '')}".casefold()
        ]
    if activity_id:
        activity = (
            client.table("activities")
            .select("id")
            .eq("id", activity_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
            .data
        )
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")
        linked_entry_ids = {
            str(checkin["entry_id"])
            for checkin in (
                client.table("activity_checkins")
                .select("entry_id")
                .eq("activity_id", activity_id)
                .eq("user_id", user_id)
                .eq("status", "approved")
                .execute()
                .data
                or []
            )
            if checkin.get("entry_id")
        }
        entries = [entry for entry in entries if str(entry["id"]) in linked_entry_ids]

    enriched = enrich_diary_entries(entries, client, user_id)
    if media_type == "audio":
        return [entry for entry in enriched if entry.audio_count]
    if media_type == "image":
        return [entry for entry in enriched if entry.image_count]
    return enriched


@app.post("/v1/diary/search-recap", response_model=SearchRecapResponse)
async def create_search_recap(
    payload: SearchRecapRequest, user_id: str = Depends(current_user_id)
) -> SearchRecapResponse:
    client = service_client()
    requested_ids = [str(entry_id) for entry_id in payload.entry_ids]
    entries = (
        client.table("diary_entries")
        .select("id, local_date, title, body")
        .eq("user_id", user_id)
        .eq("status", "approved")
        .in_("id", requested_ids)
        .execute()
        .data
        or []
    )
    if len(entries) != len(set(requested_ids)):
        raise HTTPException(
            status_code=404, detail="One or more matched diary entries were not found"
        )
    entries.sort(key=lambda entry: str(entry["local_date"]), reverse=True)
    source = "\n\n".join(
        f"ID: {entry['id']}\nDate: {entry['local_date']}\nTitle: {entry['title']}\nBody: {entry['body']}"
        for entry in entries
    )
    prompt = (
        "Summarize only the supplied approved diary entries. Do not invent events, emotions, "
        "or accomplishments. Write one concise period-level summary and one concise highlight for "
        "each supplied entry ID. Every highlight must use exactly one supplied ID."
    )
    try:
        generated = (
            structured_search_recap_model()
            .invoke([("system", prompt), ("user", source)])
            .model_dump(mode="json")
        )
    except Exception:
        log.exception("Search recap generation failed")
        raise HTTPException(status_code=503, detail="AI recap is unavailable right now")
    valid_ids = {str(entry["id"]) for entry in entries}
    highlights = [
        SearchRecapHighlightResponse(
            entry_id=highlight["entry_id"], highlight=highlight["highlight"]
        )
        for highlight in generated.get("highlights", [])
        if str(highlight.get("entry_id")) in valid_ids and highlight.get("highlight")
    ]
    return SearchRecapResponse(
        summary=generated["summary"],
        result_count=len(entries),
        date_from=min(date.fromisoformat(str(entry["local_date"])) for entry in entries),
        date_to=max(date.fromisoformat(str(entry["local_date"])) for entry in entries),
        highlights=highlights,
    )


@app.post("/v1/activities", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    payload: ActivityCreate, user_id: str = Depends(current_user_id)
) -> ActivityResponse:
    result = (
        service_client()
        .table("activities")
        .insert(
            {
                **payload.model_dump(mode="json"),
                "user_id": user_id,
                "timezone": user_timezone(user_id),
            }
        )
        .execute()
    )
    return activity_response(result.data[0])


@app.get("/v1/activities", response_model=list[ActivityResponse])
async def list_activities(
    status_filter: str = Query(default="active", alias="status"),
    user_id: str = Depends(current_user_id),
) -> list[ActivityResponse]:
    if status_filter not in {"active", "completed"}:
        raise HTTPException(status_code=422, detail="status must be active or completed")
    client = service_client()
    statuses = ["active", "paused"] if status_filter == "active" else ["completed"]
    rows = (
        client.table("activities")
        .select("*")
        .eq("user_id", user_id)
        .in_("status", statuses)
        .order("completed_at", desc=True)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    recap_rows = (
        client.table("activity_recaps")
        .select("activity_id, status")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    recap_by_activity = {str(recap["activity_id"]): recap.get("status") for recap in recap_rows}
    today = local_today(user_id)
    result: list[ActivityResponse] = []
    for row in rows:
        if row.get("status") == "active":
            row = {**row, **refresh_activity_consistency(client, row, user_id, today)}
        response = activity_response(row, recap_by_activity.get(str(row["id"])))
        response.completed_for_date = False
        response.due_for_date = activity_is_due_for_date(row, today)
        result.append(response)
    return result


@app.put("/v1/entries/today", response_model=DiaryEntryResponse)
async def upsert_today_entry(
    payload: DiaryEntryUpsert, user_id: str = Depends(current_user_id)
) -> DiaryEntryResponse:
    current_date = local_today(user_id)
    result = (
        service_client()
        .table("diary_entries")
        .upsert(
            {
                **payload.model_dump(mode="json"),
                "user_id": user_id,
                "local_date": current_date.isoformat(),
                "status": "approved",
            },
            on_conflict="user_id,local_date",
        )
        .execute()
    )
    return DiaryEntryResponse(**result.data[0])


@app.post("/v1/captures", response_model=CaptureResponse, status_code=status.HTTP_201_CREATED)
async def create_capture(
    payload: CaptureCreate, user_id: str = Depends(current_user_id)
) -> CaptureResponse:
    if payload.requested_activity_id:
        activity = (
            service_client()
            .table("activities")
            .select("id")
            .eq("id", str(payload.requested_activity_id))
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
            .data
        )
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found or not owned by user")

    current_date = local_today(user_id)
    capture_date = payload.local_date or current_date
    if capture_date > current_date:
        raise HTTPException(
            status_code=422,
            detail="A capture cannot be created for a future day",
        )
    result = (
        service_client()
        .table("captures")
        .insert(
            {
                **payload.model_dump(mode="json", exclude={"local_date"}),
                "user_id": user_id,
                "local_date": capture_date.isoformat(),
                "status": "uploaded" if payload.raw_text else "pending_upload",
            }
        )
        .execute()
    )
    return CaptureResponse(**result.data[0])


@app.post("/v1/captures/{capture_id}/upload-url", response_model=UploadUrlResponse)
async def create_upload_url(
    capture_id: str, payload: UploadUrlRequest, user_id: str = Depends(current_user_id)
) -> UploadUrlResponse:
    client = service_client()
    capture = (
        client.table("captures")
        .select("id")
        .eq("id", capture_id)
        .eq("user_id", user_id)
        .single()
        .execute()
        .data
    )
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")
    extension = payload.file_extension.lower().lstrip(".")
    if not extension.isalnum() or len(extension) > 8:
        raise HTTPException(status_code=422, detail="Invalid file extension")
    path = f"users/{user_id}/captures/{capture_id}/{payload.media_type}.{extension}"
    media = (
        client.table("media_items")
        .insert(
            {
                "user_id": user_id,
                "storage_path": path,
                "media_type": payload.media_type,
                "upload_source": "in_app" if payload.media_type == "audio" else "user_selected",
            }
        )
        .execute()
        .data[0]
    )
    client.table("capture_media").insert(
        {"capture_id": capture_id, "media_item_id": media["id"]}
    ).execute()
    signed = client.storage.from_("dayfora-media").create_signed_upload_url(path)
    return UploadUrlResponse(
        media_item_id=media["id"],
        storage_path=path,
        signed_url=signed["signedUrl"],
        token=signed["token"],
    )


CaptureProgress = Callable[[str, str], None]


def _process_capture(
    capture_id: str,
    user_id: str,
    report_progress: CaptureProgress | None = None,
) -> dict[str, Any]:
    """Retire the capture-to-draft pipeline without deleting legacy data."""

    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Capture processing is retired; save a diary entry directly at /v1/entries",
    )


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {dumps(data)}\n\n"


@app.post("/v1/captures/{capture_id}/process/events")
def stream_capture_processing(
    capture_id: str, user_id: str = Depends(current_user_id)
) -> StreamingResponse:
    """Stream safe processing milestones, never model reasoning or private chain-of-thought."""

    def event_stream() -> Iterator[str]:
        events: Queue[tuple[str, dict[str, Any] | None]] = Queue()

        def publish(stage: str, message: str) -> None:
            events.put(("progress", {"stage": stage, "message": message}))

        def process() -> None:
            try:
                result = _process_capture(capture_id, user_id, publish)
                events.put(("complete", result))
            except HTTPException as error:
                events.put(
                    (
                        "error",
                        {"detail": str(error.detail), "status": error.status_code},
                    )
                )
            except Exception:
                log.exception("Capture event stream failed for capture %s", capture_id)
                events.put(("error", {"detail": "Capture processing failed", "status": 500}))
            finally:
                events.put(("done", None))

        Thread(target=process, daemon=True).start()
        while True:
            event, data = events.get()
            if event == "done":
                return
            yield _sse_event(event, data or {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/v1/captures/{capture_id}/process")
def process_capture(capture_id: str, user_id: str = Depends(current_user_id)) -> dict[str, Any]:
    return _process_capture(capture_id, user_id)


@app.get("/v1/entries/{entry_id}/draft", response_model=DraftResponse)
async def get_draft(entry_id: str, user_id: str = Depends(current_user_id)) -> DraftResponse:
    result = (
        service_client()
        .table("drafts")
        .select("*")
        .eq("entry_id", entry_id)
        .eq("user_id", user_id)
        .eq("status", "ready_for_review")
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="No active draft found")
    return DraftResponse(**result.data)


@app.post("/v1/drafts/{draft_id}/review", response_model=ReviewResponse)
async def review_draft(
    draft_id: str, decision: DraftReview, user_id: str = Depends(current_user_id)
) -> ReviewResponse:
    draft = (
        service_client()
        .table("drafts")
        .select("*")
        .eq("id", draft_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.get("status") != "ready_for_review":
        raise HTTPException(status_code=409, detail="Draft is not in reviewable status")

    thread_id = f"diary:{user_id}:{draft['entry_id']}"
    try:
        build_graph(SupabaseTools(service_client())).invoke(
            Command(resume=decision.model_dump(mode="json")),
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception:
        log.exception("Graph resume failed for draft %s", draft_id)
        raise HTTPException(status_code=500, detail="Review processing failed")

    return ReviewResponse(
        status="discarded" if decision.action == "discard" else "approved",
        entry_id=draft["entry_id"],
    )


# ---------------------------------------------------------------------------
# Activity check-ins
# ---------------------------------------------------------------------------


@app.get("/v1/activities/{activity_id}/checkins", response_model=list[CheckinResponse])
async def list_checkins(
    activity_id: str, user_id: str = Depends(current_user_id)
) -> list[CheckinResponse]:
    client = service_client()
    activity = (
        client.table("activities")
        .select("id")
        .eq("id", activity_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    result = (
        client.table("activity_checkins")
        .select("*")
        .eq("activity_id", activity_id)
        .eq("user_id", user_id)
        .order("local_date", desc=True)
        .execute()
    )
    return [CheckinResponse(**row) for row in (result.data or [])]


@app.get("/v1/activities/{activity_id}/events", response_model=list[ActivityEventResponse])
async def list_activity_events(
    activity_id: str, user_id: str = Depends(current_user_id)
) -> list[ActivityEventResponse]:
    client = service_client()
    activity = (
        client.table("activities")
        .select("*")
        .eq("id", activity_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.get("status") == "active":
        refresh_activity_consistency(client, activity, user_id, local_today(user_id))
    rows = (
        client.table("activity_events")
        .select("*")
        .eq("activity_id", activity_id)
        .eq("user_id", user_id)
        .order("local_date", desc=True)
        .execute()
        .data
        or []
    )
    return [ActivityEventResponse(**row) for row in rows]


@app.post(
    "/v1/activities/{activity_id}/checkins",
    response_model=CheckinResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_checkin(
    activity_id: str, payload: CheckinCreate, user_id: str = Depends(current_user_id)
) -> CheckinResponse:
    client = service_client()
    activity = (
        client.table("activities")
        .select("*")
        .eq("id", activity_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.get("status") != "active":
        raise HTTPException(
            status_code=409, detail="Progress can only be logged for an active activity"
        )

    checkin_date = payload.local_date or local_today(user_id)
    if checkin_date > local_today(user_id) or not activity_is_due_for_date(activity, checkin_date):
        raise HTTPException(
            status_code=422, detail="This activity is not eligible for progress on that date"
        )
    result = (
        client.table("activity_checkins")
        .upsert(
            {
                "activity_id": activity_id,
                "user_id": user_id,
                "local_date": checkin_date.isoformat()
                if hasattr(checkin_date, "isoformat")
                else str(checkin_date),
                "milestone": payload.milestone,
                "note": payload.note,
                "next_small_step": payload.next_small_step,
                "status": "approved",
            },
            on_conflict="activity_id,local_date",
        )
        .execute()
    )
    checkin = result.data[0]
    client.table("activity_events").upsert(
        {
            "activity_id": activity_id,
            "user_id": user_id,
            "local_date": checkin["local_date"],
            "event_type": "checkin",
            "checkin_id": checkin["id"],
        },
        on_conflict="activity_id,local_date,event_type",
    ).execute()
    refresh_activity_consistency(client, activity, user_id, local_today(user_id))
    return CheckinResponse(**checkin)


@app.post("/v1/activities/{activity_id}/status", response_model=ActivityResponse)
async def update_activity_status(
    activity_id: str, payload: ActivityStatusUpdate, user_id: str = Depends(current_user_id)
) -> ActivityResponse:
    client = service_client()
    activity = (
        client.table("activities")
        .select("*")
        .eq("id", activity_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.get("status") == "completed":
        raise HTTPException(status_code=409, detail="A completed activity cannot be resumed")
    updated = (
        client.table("activities")
        .update({"status": payload.status})
        .eq("id", activity_id)
        .eq("user_id", user_id)
        .execute()
        .data[0]
    )
    client.table("activity_events").upsert(
        {
            "activity_id": activity_id,
            "user_id": user_id,
            "local_date": local_today(user_id).isoformat(),
            "event_type": "paused" if payload.status == "paused" else "resumed",
        },
        on_conflict="activity_id,local_date,event_type",
    ).execute()
    return activity_response(updated)


@app.post("/v1/activities/{activity_id}/complete", response_model=ActivityRecapResponse)
async def complete_activity(
    activity_id: str, user_id: str = Depends(current_user_id)
) -> ActivityRecapResponse:
    """Only the user can complete an activity; the resulting recap remains reviewable."""
    client = service_client()
    activity = (
        client.table("activities")
        .select("*")
        .eq("id", activity_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    existing = (
        client.table("activity_recaps")
        .select("*")
        .eq("activity_id", activity_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if existing:
        return ActivityRecapResponse(**existing)
    checkins = (
        client.table("activity_checkins")
        .select("local_date, milestone, note, next_small_step")
        .eq("activity_id", activity_id)
        .eq("user_id", user_id)
        .eq("status", "approved")
        .order("local_date")
        .limit(50)
        .execute()
        .data
        or []
    )
    evidence = "\n".join(
        f"{item['local_date']}: {item['milestone']}"
        + (f" — {item['note']}" if item.get("note") else "")
        for item in checkins
    )
    try:
        generated = (
            structured_activity_recap_model()
            .invoke(
                [
                    (
                        "system",
                        "Write a private, faithful proof-of-progress recap using only the supplied approved "
                        "milestones. Never claim completion on behalf of the user or invent evidence.",
                    ),
                    (
                        "user",
                        f"Activity: {activity['title']}\nWhy: {activity.get('purpose') or ''}\n\n{evidence}",
                    ),
                ]
            )
            .model_dump(mode="json")
        )
    except Exception:
        log.exception("Activity recap generation failed")
        raise HTTPException(status_code=503, detail="Proof recap is unavailable right now")
    completed_at = datetime.now(UTC).isoformat()
    client.table("activities").update({"status": "completed", "completed_at": completed_at}).eq(
        "id", activity_id
    ).eq("user_id", user_id).execute()
    client.table("activity_events").upsert(
        {
            "activity_id": activity_id,
            "user_id": user_id,
            "local_date": local_today(user_id).isoformat(),
            "event_type": "completed",
        },
        on_conflict="activity_id,local_date,event_type",
    ).execute()
    recap = (
        client.table("activity_recaps")
        .insert(
            {
                "activity_id": activity_id,
                "user_id": user_id,
                "payload": {**generated, "source_checkin_count": len(checkins)},
                "status": "ready_for_review",
            }
        )
        .execute()
        .data[0]
    )
    return ActivityRecapResponse(**recap)


@app.get("/v1/activities/{activity_id}/recap", response_model=ActivityRecapResponse | None)
async def get_activity_recap(
    activity_id: str, user_id: str = Depends(current_user_id)
) -> ActivityRecapResponse | None:
    result = (
        service_client()
        .table("activity_recaps")
        .select("*")
        .eq("activity_id", activity_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    recap = result.data if result else None
    return ActivityRecapResponse(**recap) if recap else None


@app.post("/v1/activity-recaps/{recap_id}/review", response_model=ReviewResponse)
async def review_activity_recap(
    recap_id: str, decision: ActivityRecapReview, user_id: str = Depends(current_user_id)
) -> ReviewResponse:
    client = service_client()
    recap = (
        client.table("activity_recaps")
        .select("id, activity_id, status")
        .eq("id", recap_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not recap:
        raise HTTPException(status_code=404, detail="Proof recap not found")
    if recap.get("status") != "ready_for_review":
        raise HTTPException(status_code=409, detail="Proof recap is not reviewable")
    new_status = "approved" if decision.action == "approve" else "discarded"
    client.table("activity_recaps").update({"status": new_status}).eq("id", recap_id).execute()
    return ReviewResponse(status=new_status, entry_id=recap["activity_id"])


@app.get("/v1/activities/search", response_model=list[ActivitySearchResult])
async def search_activities(
    query: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    media_type: str | None = Query(default=None, pattern="^(audio|image)$"),
    user_id: str = Depends(current_user_id),
) -> list[ActivitySearchResult]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    client = service_client()
    activities = client.table("activities").select("*").eq("user_id", user_id).execute().data or []
    checkins_query = (
        client.table("activity_checkins")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "approved")
    )
    if date_from:
        checkins_query = checkins_query.gte("local_date", date_from.isoformat())
    if date_to:
        checkins_query = checkins_query.lte("local_date", date_to.isoformat())
    checkins = checkins_query.order("local_date", desc=True).execute().data or []
    normalized = (query or "").strip().casefold()
    matching_media_checkins: set[str] | None = None
    if media_type:
        links = (
            client.table("checkin_media").select("checkin_id, media_item_id").execute().data or []
        )
        media_ids = [str(link["media_item_id"]) for link in links]
        media = (
            client.table("media_items")
            .select("id")
            .eq("user_id", user_id)
            .eq("media_type", media_type)
            .in_("id", media_ids)
            .execute()
            .data
            or []
            if media_ids
            else []
        )
        matching_ids = {str(item["id"]) for item in media}
        matching_media_checkins = {
            str(link["checkin_id"]) for link in links if str(link["media_item_id"]) in matching_ids
        }
    by_activity: dict[str, list[dict[str, Any]]] = {}
    for checkin in checkins:
        if (
            matching_media_checkins is not None
            and str(checkin["id"]) not in matching_media_checkins
        ):
            continue
        haystack = f"{checkin.get('milestone', '')}\n{checkin.get('note', '')}".casefold()
        if normalized and normalized not in haystack:
            continue
        by_activity.setdefault(str(checkin["activity_id"]), []).append(checkin)
    results: list[ActivitySearchResult] = []
    for activity in activities:
        activity_text = f"{activity.get('title', '')}\n{activity.get('purpose', '')}".casefold()
        matches = by_activity.get(str(activity["id"]), [])
        if normalized and normalized not in activity_text and not matches:
            continue
        if (date_from or date_to or media_type) and not matches:
            continue
        results.append(
            ActivitySearchResult(
                activity=activity_response(activity), matching_checkins=matches[:10]
            )
        )
    return results


# ---------------------------------------------------------------------------
# Device tokens
# ---------------------------------------------------------------------------


@app.post("/v1/device-tokens", status_code=status.HTTP_201_CREATED)
async def register_device_token(
    payload: DeviceTokenCreate, user_id: str = Depends(current_user_id)
) -> dict[str, str]:
    client = service_client()
    client.table("device_tokens").upsert(
        {
            "user_id": user_id,
            "expo_push_token": payload.expo_push_token,
            "platform": payload.platform,
        },
        on_conflict="expo_push_token",
    ).execute()
    return {"status": "registered"}


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------


@app.get("/v1/notification-preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    user_id: str = Depends(current_user_id),
) -> NotificationPreferencesResponse:
    result = (
        service_client()
        .table("notification_preferences")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        return NotificationPreferencesResponse(
            user_id=user_id,
            timezone="UTC",
            diary_enabled=False,
            activity_enabled=False,
            weekly_recap_enabled=False,
        )
    return NotificationPreferencesResponse(**result.data)


@app.put("/v1/notification-preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    payload: NotificationPreferencesUpdate, user_id: str = Depends(current_user_id)
) -> NotificationPreferencesResponse:
    client = service_client()
    updates = {k: v for k, v in payload.model_dump(mode="json").items() if v is not None}
    if updates:
        client.table("notification_preferences").update(updates).eq("user_id", user_id).execute()
    result = (
        client.table("notification_preferences")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    return (
        NotificationPreferencesResponse(**result.data)
        if result and result.data
        else NotificationPreferencesResponse(
            user_id=user_id,
            timezone="UTC",
            diary_enabled=False,
            activity_enabled=False,
            weekly_recap_enabled=False,
        )
    )


# ---------------------------------------------------------------------------
# Weekly recaps
# ---------------------------------------------------------------------------


@app.post("/v1/internal/reminders/dispatch")
async def dispatch_reminders(x_job_token: str | None = Header(default=None)) -> dict[str, int]:
    expected = os.getenv("DAYFORA_JOB_TOKEN")
    if not expected or x_job_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid job token")
    return {"dispatched": dispatch_due_reminders(service_client())}


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


@app.post(
    "/v1/recaps/trigger", response_model=WeeklyRecapResponse, status_code=status.HTTP_201_CREATED
)
async def trigger_weekly_recap(
    user_id: str = Depends(current_user_id),
) -> WeeklyRecapResponse:
    client = service_client()
    today = local_today(user_id)
    week_start = _week_start(today)
    week_end = week_start + timedelta(days=6)

    existing = (
        client.table("weekly_recaps")
        .select("*")
        .eq("user_id", user_id)
        .eq("week_start_date", week_start.isoformat())
        .maybe_single()
        .execute()
    )
    if existing and existing.data:
        return WeeklyRecapResponse(**existing.data)

    entries = (
        client.table("diary_entries")
        .select("title, body, mood, day_feeling, local_date")
        .eq("user_id", user_id)
        .gte("local_date", week_start.isoformat())
        .lte("local_date", week_end.isoformat())
        .eq("status", "approved")
        .order("local_date")
        .execute()
        .data
        or []
    )

    checkins = (
        client.table("activity_checkins")
        .select("milestone, note, local_date, activity_id, activities(title)")
        .eq("user_id", user_id)
        .gte("local_date", week_start.isoformat())
        .lte("local_date", week_end.isoformat())
        .eq("status", "approved")
        .order("local_date")
        .execute()
        .data
        or []
    )

    payload = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "entries": entries,
        "checkins": checkins,
        "entry_count": len(entries),
        "checkin_count": len(checkins),
    }

    result = (
        client.table("weekly_recaps")
        .insert(
            {
                "user_id": user_id,
                "week_start_date": week_start.isoformat(),
                "payload": payload,
                "status": "ready_for_review",
            }
        )
        .execute()
    )
    return WeeklyRecapResponse(**result.data[0])


@app.get("/v1/recaps/current", response_model=WeeklyRecapResponse | None)
async def get_current_recap(
    user_id: str = Depends(current_user_id),
) -> WeeklyRecapResponse | None:
    today = local_today(user_id)
    week_start = _week_start(today)
    result = (
        service_client()
        .table("weekly_recaps")
        .select("*")
        .eq("user_id", user_id)
        .eq("week_start_date", week_start.isoformat())
        .maybe_single()
        .execute()
    )
    return WeeklyRecapResponse(**result.data) if result and result.data else None


@app.post("/v1/recaps/{recap_id}/review", response_model=ReviewResponse)
async def review_recap(
    recap_id: str, decision: DraftReview, user_id: str = Depends(current_user_id)
) -> ReviewResponse:
    client = service_client()
    recap = (
        client.table("weekly_recaps")
        .select("*")
        .eq("id", recap_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not recap:
        raise HTTPException(status_code=404, detail="Recap not found")
    if recap.get("status") != "ready_for_review":
        raise HTTPException(status_code=409, detail="Recap is not in reviewable status")

    new_status = "discarded" if decision.action == "discard" else "approved"
    client.table("weekly_recaps").update({"status": new_status}).eq("id", recap_id).execute()
    return ReviewResponse(status=new_status, entry_id=recap_id)


# Diary-first v1 endpoints. These are additive while legacy data remains
# readable; the mobile v1 client does not invoke capture, draft or activity APIs.


def _owned_media(client: Client, user_id: str, media_ids: list[str]) -> list[dict[str, Any]]:
    if not media_ids:
        return []
    rows = (
        client.table("media_items")
        .select("id, media_type, upload_status")
        .eq("user_id", user_id)
        .in_("id", media_ids)
        .execute()
        .data
        or []
    )
    if len(rows) != len(set(media_ids)):
        raise HTTPException(status_code=404, detail="One or more attachments were not found")
    return rows


def resolve_saved_direct_entry(
    client: Client,
    write_response: Any,
    user_id: str,
    local_date: date,
) -> dict[str, Any]:
    """Resolve a direct-save write even when PostgREST returns minimal data."""
    data = optional_response_data(write_response)
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        return data

    reread = (
        client.table("diary_entries")
        .select("id, user_id, local_date, title, body, mood_v1, status, created_at, updated_at")
        .eq("user_id", user_id)
        .eq("local_date", local_date.isoformat())
        .maybe_single()
        .execute()
    )
    saved = optional_response_data(reread)
    if not saved:
        raise HTTPException(
            status_code=502, detail="Diary entry could not be confirmed after saving"
        )
    return saved


@app.post(
    "/v1/media/upload-url", response_model=MediaUploadResponse, status_code=status.HTTP_201_CREATED
)
async def create_v1_media_upload_url(
    payload: MediaUploadRequest, user_id: str = Depends(current_user_id)
) -> MediaUploadResponse:
    extension = payload.file_extension.lower()
    path = f"users/{user_id}/entries/unattached/{uuid4()}.{extension}"
    client = service_client()
    media = (
        client.table("media_items")
        .insert(
            {
                "user_id": user_id,
                "storage_path": path,
                "media_type": payload.media_type,
                "upload_source": "in_app" if payload.media_type == "audio" else "user_selected",
                "upload_status": "pending",
            }
        )
        .execute()
        .data[0]
    )
    signed = client.storage.from_("dayfora-media").create_signed_upload_url(path)
    return MediaUploadResponse(
        media_item_id=media["id"],
        storage_path=path,
        signed_url=signed["signedUrl"],
        token=signed["token"],
    )


@app.post("/v1/entries", response_model=DiaryEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_direct_entry(
    payload: DiaryEntryWrite, user_id: str = Depends(current_user_id)
) -> DiaryEntryResponse:
    today = local_today(user_id)
    entry_date = payload.local_date or today
    if entry_date > today:
        raise HTTPException(status_code=422, detail="A future diary entry cannot be created")
    client = service_client()
    media = _owned_media(client, user_id, [str(value) for value in payload.media_item_ids])
    existing_response = (
        client.table("diary_entries")
        .select("id, local_date")
        .eq("user_id", user_id)
        .eq("local_date", entry_date.isoformat())
        .maybe_single()
        .execute()
    )
    existing = optional_response_data(existing_response)
    if existing and entry_date < today:
        raise HTTPException(
            status_code=409, detail="Past entries are preserved; add a reflection instead"
        )
    values = {
        "user_id": user_id,
        "local_date": entry_date.isoformat(),
        "title": payload.title,
        "body": payload.body.strip() if payload.body else None,
        "mood_v1": payload.mood,
        "status": "approved",
        "v1_saved_at": datetime.now(UTC).isoformat(),
    }
    write_response = (
        client.table("diary_entries").upsert(values, on_conflict="user_id,local_date").execute()
    )
    saved = resolve_saved_direct_entry(client, write_response, user_id, entry_date)
    if payload.media_item_ids:
        links = [
            {"entry_id": saved["id"], "media_item_id": str(media_id), "role": "attachment"}
            for media_id in payload.media_item_ids
        ]
        client.table("entry_media").upsert(links, on_conflict="entry_id,media_item_id").execute()
        client.table("media_items").update({"upload_status": "uploaded"}).eq(
            "user_id", user_id
        ).in_("id", [str(item["id"]) for item in media]).execute()
    _index_entry_text_embedding(client, {**saved, "user_id": user_id})
    return present_v1_entries([saved], client, user_id)[0]


@app.patch("/v1/entries/{entry_id}", response_model=DiaryEntryResponse)
async def update_today_direct_entry(
    entry_id: str, payload: DiaryEntryWrite, user_id: str = Depends(current_user_id)
) -> DiaryEntryResponse:
    today = local_today(user_id)
    client = service_client()
    entry_response = (
        client.table("diary_entries")
        .select("id, local_date")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    entry = optional_response_data(entry_response)
    if not entry:
        raise HTTPException(status_code=404, detail="Diary entry not found")
    if date.fromisoformat(entry["local_date"]) != today:
        raise HTTPException(
            status_code=409, detail="Past entries are preserved; add a reflection instead"
        )
    media = _owned_media(client, user_id, [str(value) for value in payload.media_item_ids])
    write_response = (
        client.table("diary_entries")
        .update(
            {
                "title": payload.title,
                "body": payload.body.strip() if payload.body else None,
                "mood_v1": payload.mood,
                "v1_saved_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .execute()
    )
    saved = resolve_saved_direct_entry(client, write_response, user_id, today)
    if payload.media_item_ids:
        client.table("entry_media").upsert(
            [
                {"entry_id": entry_id, "media_item_id": str(media_id), "role": "attachment"}
                for media_id in payload.media_item_ids
            ],
            on_conflict="entry_id,media_item_id",
        ).execute()
        client.table("media_items").update({"upload_status": "uploaded"}).eq(
            "user_id", user_id
        ).in_("id", [str(item["id"]) for item in media]).execute()
    _index_entry_text_embedding(client, {**saved, "user_id": user_id})
    return present_v1_entries([saved], client, user_id)[0]


@app.get("/v1/explore/discover", response_model=ExploreDiscoveryResponse)
async def discover_explore(user_id: str = Depends(current_user_id)) -> ExploreDiscoveryResponse:
    client = service_client()
    today = local_today(user_id)
    entries = (
        client.table("diary_entries")
        .select("id, user_id, local_date, title, body, mood_v1, created_at, updated_at")
        .eq("user_id", user_id)
        .eq("status", "approved")
        .order("local_date", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )
    normalized = [{**entry, "mood": entry.get("mood_v1")} for entry in entries]
    on_this_day = [
        entry
        for entry in normalized
        if entry["local_date"][5:] == today.isoformat()[5:]
        and entry["local_date"][:4] != today.isoformat()[:4]
    ]
    recap_rows = (
        client.table("recaps")
        .select("*")
        .eq("user_id", user_id)
        .order("period_start_date", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    recaps = [
        RecapResponse(
            id=row["id"],
            recap_type=row["recap_type"],
            period_start_date=row["period_start_date"],
            period_end_date=row["period_end_date"],
            title=row["payload"].get("title"),
            summary=row["payload"].get("summary"),
            source_count=len(row["payload"].get("source_entry_ids", [])),
            saved=True,
        )
        for row in recap_rows
    ]
    entry_by_id = {str(entry["id"]): entry for entry in entries}
    entry_links = (
        client.table("entry_media")
        .select("entry_id, media_item_id")
        .in_("entry_id", list(entry_by_id))
        .execute()
        .data
        or []
        if entry_by_id
        else []
    )
    media_ids = [str(link["media_item_id"]) for link in entry_links if link.get("media_item_id")]
    media_rows = (
        client.table("media_items")
        .select("id, media_type, storage_path, upload_status")
        .eq("user_id", user_id)
        .in_("id", media_ids)
        .execute()
        .data
        or []
        if media_ids
        else []
    )
    media_by_id = {str(media["id"]): media for media in media_rows}
    links_by_entry: dict[str, list[str]] = {}
    for link in entry_links:
        entry_id = str(link.get("entry_id", ""))
        media_id = str(link.get("media_item_id", ""))
        if entry_id in entry_by_id and media_id in media_by_id:
            links_by_entry.setdefault(entry_id, []).append(media_id)

    def recent_media(media_type: str, limit: int) -> list[ExploreMediaItem]:
        result: list[ExploreMediaItem] = []
        for entry in entries:
            for media_id in links_by_entry.get(str(entry["id"]), []):
                media = media_by_id[media_id]
                if media.get("media_type") != media_type:
                    continue
                signed = client.storage.from_("dayfora-media").create_signed_url(
                    media["storage_path"], 900
                )
                signed_url = signed.get("signedURL") or signed.get("signedUrl")
                if not signed_url:
                    log.warning("Unable to create private Explore media URL for %s", media_id)
                    continue
                result.append(
                    ExploreMediaItem(
                        entry_id=entry["id"],
                        media_item_id=media_id,
                        title=entry["title"],
                        local_date=entry["local_date"],
                        signed_url=signed_url,
                    )
                )
                if len(result) == limit:
                    return result
        return result

    return ExploreDiscoveryResponse(
        on_this_day=present_v1_entries(on_this_day, client, user_id),
        saved_recaps=recaps,
        recent_photos=recent_media("image", 9),
        recent_audio=recent_media("audio", 6),
    )


def _matching_v1_entries(
    client: Client,
    user_id: str,
    *,
    query: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    mood: str | None = None,
    entry_ids: list[str] | None = None,
    limit: int = 20,
    title_only: bool = False,
) -> list[dict[str, Any]]:
    request = (
        client.table("diary_entries")
        .select("id, local_date, title, body, mood, mood_v1")
        .eq("user_id", user_id)
        .eq("status", "approved")
        .order("local_date", desc=True)
        # Apply visible filters in PostgREST first, then rank a bounded
        # candidate window. Retrieval never widens ownership or approval scope.
        .limit(max(limit, 100))
    )
    if date_from:
        request = request.gte("local_date", date_from.isoformat())
    if date_to:
        request = request.lte("local_date", date_to.isoformat())
    if entry_ids:
        request = request.in_("id", entry_ids)
    rows = request.execute().data or []
    if mood:
        rows = [row for row in rows if explicit_entry_mood(row) == mood]
    semantic_scores = _semantic_entry_scores(client, user_id, query)
    return rank_hybrid_entries(
        rows,
        query,
        title_only=title_only,
        semantic_scores=semantic_scores,
        limit=limit,
    )


def _semantic_entry_scores(client: Client, user_id: str, query: str | None) -> dict[str, float]:
    """Return optional pgvector scores without making semantic search mandatory.

    The Supabase ``embed-diary-text`` function uses the hosted gte-small model.
    Local/dev environments can leave ``DAYFORA_SEMANTIC_SEARCH`` unset: exact
    and close-token hybrid retrieval remains fully functional.  Any provider or
    RPC failure is contained and never turns a diary search into a 500.
    """

    if not query or os.getenv("DAYFORA_SEMANTIC_SEARCH", "").casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return {}
    try:
        response = client.functions.invoke(
            os.getenv("DAYFORA_EMBEDDING_FUNCTION", "embed-diary-text"),
            {"body": {"input": query}, "responseType": "json"},
        )
        payload = response if isinstance(response, dict) else {}
        embedding = payload.get("embedding")
        if not isinstance(embedding, list) or len(embedding) != 384:
            return {}
        result = client.rpc(
            "match_diary_entry_embeddings",
            {
                "query_embedding": embedding,
                "match_threshold": 0.42,
                "match_count": 50,
                "requested_user_id": user_id,
            },
        ).execute()
        return {
            str(row["entry_id"]): float(row["similarity"])
            for row in (result.data or [])
            if row.get("entry_id") is not None and row.get("similarity") is not None
        }
    except Exception as exc:  # pragma: no cover - provider is optional in unit tests
        log.info("Semantic diary retrieval unavailable; using lexical ranking: %s", exc)
        return {}


def _index_entry_text_embedding(client: Client, entry: dict[str, Any]) -> None:
    """Best-effort indexing of a saved title/body when semantic search is enabled."""

    if os.getenv("DAYFORA_SEMANTIC_SEARCH", "").casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    source_text = f"{entry.get('title') or ''}\n{entry.get('body') or ''}".strip()
    if not source_text or not entry.get("id") or not entry.get("user_id"):
        return
    try:
        response = client.functions.invoke(
            os.getenv("DAYFORA_EMBEDDING_FUNCTION", "embed-diary-text"),
            {"body": {"input": source_text}, "responseType": "json"},
        )
        payload = response if isinstance(response, dict) else {}
        embedding = payload.get("embedding")
        if not isinstance(embedding, list) or len(embedding) != 384:
            return
        client.table("diary_entry_embeddings").upsert(
            {
                "entry_id": str(entry["id"]),
                "user_id": str(entry["user_id"]),
                "content": source_text,
                "content_hash": md5(source_text.encode()).hexdigest(),
                "embedding": embedding,
                "model": payload.get("model", "Supabase/gte-small"),
            },
            on_conflict="entry_id",
        ).execute()
    except Exception as exc:  # pragma: no cover - provider is optional in unit tests
        log.info("Semantic diary indexing unavailable; saved entry remains searchable: %s", exc)


def agent_scoped_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the only diary fields that may enter a LangGraph memory request.

    Ownership and visible filtering have already been performed by callers.
    In particular, this intentionally excludes media IDs, private storage paths,
    signed URLs, processing metadata, addenda, and legacy draft fields.
    """

    return [
        {
            "id": str(entry["id"]),
            "local_date": str(entry["local_date"]),
            "title": str(entry["title"]),
            "body": str(entry["body"]) if entry.get("body") is not None else None,
            "mood": explicit_entry_mood(entry),
        }
        for entry in entries[:20]
    ]


def explicit_entry_mood(entry: dict[str, Any]) -> str | None:
    """Accept the direct-save mood field and the retained legacy field during migration."""
    return entry.get("mood_v1") or entry.get("mood")


def entry_matches_search_words(
    entry: dict[str, Any], words: list[str], *, title_only: bool
) -> bool:
    return hybrid_entry_score(entry, " ".join(words), title_only=title_only) >= 0.32


def filter_v1_media_presence(
    entries: list[dict[str, Any]], client: Client, user_id: str, media_type: str | None
) -> list[dict[str, Any]]:
    """Apply a visible attachment-presence filter; never inspect media content."""
    if not media_type:
        return entries
    presented = present_v1_entries(entries, client, user_id)
    matched_ids = {
        str(entry.id)
        for entry in presented
        if (media_type == "audio" and entry.audio_count)
        or (media_type == "image" and entry.image_count)
    }
    return [entry for entry in entries if str(entry["id"]) in matched_ids]


@app.post("/v1/explore/ask", response_model=AskDiaryResponse)
async def ask_your_diary(
    payload: AskDiaryRequest, user_id: str = Depends(current_user_id)
) -> AskDiaryResponse:
    client = service_client()
    entries = _matching_v1_entries(
        client,
        user_id,
        query=payload.query,
        date_from=payload.date_from,
        date_to=payload.date_to,
        mood=payload.mood,
        entry_ids=[str(entry_id) for entry_id in payload.entry_ids],
    )
    entries = filter_v1_media_presence(entries, client, user_id, payload.media_type)
    if not entries:
        raise HTTPException(status_code=404, detail="No saved written entries matched this request")
    run_id = payload.run_id or str(uuid4())
    graph = build_memory_graph(synthesize_memory_result)
    output = graph.invoke(
        {
            "run_id": run_id,
            "user_id": user_id,
            "trigger": "ask_diary",
            "query": payload.query,
            "filters": payload.model_dump(mode="json"),
            "source_entries": agent_scoped_entries(entries),
        },
        {"configurable": {"thread_id": f"ask:{user_id}:{run_id}"}},
    )
    if output.get("errors"):
        raise HTTPException(status_code=422, detail="Unable to validate memory sources")
    result = output["result"]
    source_ids = {str(entry_id) for entry_id in result["source_entry_ids"]}
    sources = [
        SourceCard(
            entry_id=row["id"],
            local_date=row["local_date"],
            title=row["title"],
            excerpt=row.get("body"),
        )
        for row in entries
        if str(row["id"]) in source_ids
    ]
    source_dates = [
        date.fromisoformat(str(row["local_date"]))
        for row in entries
        if str(row["id"]) in source_ids
    ]
    return AskDiaryResponse(
        answer=result["answer"],
        source_count=len(sources),
        date_from=min(source_dates),
        date_to=max(source_dates),
        sources=sources,
        reflection_prompt=result.get("reflection_prompt"),
    )


@app.get("/v1/explore/search", response_model=list[DiaryEntryResponse])
async def search_explore(
    query: str | None = Query(default=None, max_length=240),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    mood: str | None = Query(default=None),
    media_type: str | None = Query(default=None),
    user_id: str = Depends(current_user_id),
) -> list[DiaryEntryResponse]:
    filters = DiarySearchFilters(
        query=query, date_from=date_from, date_to=date_to, mood=mood, media_type=media_type
    )
    client = service_client()
    entries = _matching_v1_entries(
        client,
        user_id,
        query=filters.query,
        date_from=filters.date_from,
        date_to=filters.date_to,
        mood=filters.mood,
        limit=50,
        title_only=True,
    )
    presented = present_v1_entries(entries, client, user_id)
    if filters.media_type == "audio":
        return [entry for entry in presented if entry.audio_count]
    if filters.media_type == "image":
        return [entry for entry in presented if entry.image_count]
    return presented


@app.get("/v1/memories", include_in_schema=False, deprecated=True)
async def legacy_memories_redirect() -> RedirectResponse:
    """Temporary route migration for old installed clients; new clients use Explore."""
    return RedirectResponse(
        url="/v1/explore/discover", status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@app.post("/v1/memories/ask", include_in_schema=False, deprecated=True)
async def legacy_memories_ask_redirect() -> RedirectResponse:
    """Old mobile builds receive an explicit redirect without retaining a second API flow."""
    return RedirectResponse(url="/v1/explore/ask", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.post("/v1/recaps", response_model=RecapResponse)
async def generate_v1_recap(
    payload: RecapRequest, user_id: str = Depends(current_user_id)
) -> RecapResponse:
    entries = _matching_v1_entries(
        service_client(),
        user_id,
        date_from=payload.period_start_date,
        date_to=payload.period_end_date,
    )
    eligible = entries
    if len(eligible) < 2:
        return RecapResponse(
            recap_type=payload.recap_type,
            period_start_date=payload.period_start_date,
            period_end_date=payload.period_end_date,
            source_count=len(eligible),
            insufficient_material=True,
        )
    run_id = payload.run_id or str(uuid4())
    output = build_memory_graph(synthesize_memory_result).invoke(
        {
            "run_id": run_id,
            "user_id": user_id,
            "trigger": "recap",
            "period": {
                "start": str(payload.period_start_date),
                "end": str(payload.period_end_date),
            },
            "filters": {},
            "source_entries": agent_scoped_entries(eligible),
        },
        {
            "configurable": {
                "thread_id": (
                    f"recap:{user_id}:{payload.period_start_date}:{payload.period_end_date}:{run_id}"
                )
            }
        },
    )
    if output.get("errors"):
        raise HTTPException(status_code=422, detail="Unable to validate recap sources")
    result = output["result"]
    source_ids = {str(entry_id) for entry_id in result["source_entry_ids"]}
    return RecapResponse(
        recap_type=payload.recap_type,
        period_start_date=payload.period_start_date,
        period_end_date=payload.period_end_date,
        title=result["title"],
        summary=result["summary"],
        source_count=len(source_ids),
        highlights=[
            SourceCard(
                entry_id=row["id"],
                local_date=row["local_date"],
                title=row["title"],
                excerpt=row.get("body"),
            )
            for row in eligible
            if str(row["id"]) in source_ids
        ],
        reflection_prompt=result.get("reflection_prompt"),
    )
