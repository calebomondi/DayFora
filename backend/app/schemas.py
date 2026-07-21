from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

Mood = Literal["happy_fun", "sad_dull", "mixed", "quiet"]
MediaType = Literal["audio", "image"]


def title_word_count(value: str) -> int:
    return len(value.strip().split())


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ProfileResponse(BaseModel):
    onboarding_completed_at: datetime | None = None
    created_at: datetime | None = None


class DiaryEntryWrite(BaseModel):
    local_date: date | None = None
    title: str = Field(min_length=1, max_length=240)
    body: str | None = Field(default=None, max_length=20_000)
    mood: Mood | None = None
    media_item_ids: list[UUID] = Field(default_factory=list, max_length=12)

    @field_validator("title")
    @classmethod
    def valid_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A title is required")
        if title_word_count(value) > 10:
            raise ValueError("A title may contain at most 10 words")
        return value

    @model_validator(mode="after")
    def body_or_media(self) -> "DiaryEntryWrite":
        if not (self.body or "").strip() and not self.media_item_ids:
            raise ValueError("Add a written description, voice note, or photo")
        return self


class DiaryMediaPreview(BaseModel):
    """A short-lived, entry-owned attachment preview for the diary list."""

    id: UUID
    media_type: MediaType
    signed_url: str


class DiaryEntryResponse(BaseModel):
    id: UUID
    local_date: date
    title: str
    body: str | None = None
    mood: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    audio_count: int = 0
    image_count: int = 0
    addenda_count: int = 0
    preview_images: list[DiaryMediaPreview] = Field(default_factory=list)
    preview_audio: DiaryMediaPreview | None = None
    # Legacy-only response fields. The diary-first mobile UI intentionally does
    # not render provenance or AI-derived labels.
    status: str = "approved"
    source_badge: Literal["user_written", "ai_generated"] = "user_written"
    day_feeling: str | None = None


class MediaUploadRequest(BaseModel):
    media_type: MediaType
    file_extension: str = Field(min_length=1, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    content_type: str = Field(min_length=3, max_length=120)


class MediaUploadResponse(BaseModel):
    media_item_id: UUID
    storage_path: str
    signed_url: str
    token: str


class EntryMediaResponse(BaseModel):
    id: UUID
    media_type: MediaType
    signed_url: str
    # Retained for legacy data export/read compatibility; never requested by
    # diary-first UI or passed to the v1 agent.
    transcript: str | None = None
    ai_description: dict | None = None


class DiaryAddendumCreate(BaseModel):
    body: str | None = Field(default=None, max_length=20_000)
    media_item_ids: list[UUID] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def body_or_media(self) -> "DiaryAddendumCreate":
        if not (self.body or "").strip() and not self.media_item_ids:
            raise ValueError("Add a reflection or attachment")
        return self


class DiaryAddendumResponse(BaseModel):
    id: UUID
    entry_id: UUID
    body: str | None = None
    created_at: datetime
    media: list[EntryMediaResponse] = Field(default_factory=list)


class ExploreResponse(BaseModel):
    selected_date: date
    is_today: bool
    entry: DiaryEntryResponse | None = None
    recap_available: bool = False


class ExploreMediaItem(BaseModel):
    entry_id: UUID
    media_item_id: UUID
    title: str
    local_date: date
    signed_url: str


class ExploreDiscoveryResponse(BaseModel):
    on_this_day: list[DiaryEntryResponse] = Field(default_factory=list)
    saved_recaps: list["RecapResponse"] = Field(default_factory=list)
    saved_entries: list[DiaryEntryResponse] = Field(default_factory=list)
    recent_photos: list[ExploreMediaItem] = Field(default_factory=list)
    recent_audio: list[ExploreMediaItem] = Field(default_factory=list)


# Compatibility type for the retired /v1/memories read alias. New clients use
# ExploreDiscoveryResponse through /v1/explore/discover.
MemoriesResponse = ExploreDiscoveryResponse


class DiarySearchFilters(BaseModel):
    query: str | None = Field(default=None, max_length=240)
    date_from: date | None = None
    date_to: date | None = None
    mood: Mood | None = None
    media_type: MediaType | None = None
    entry_ids: list[UUID] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def valid_range(self) -> "DiarySearchFilters":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be on or before date_to")
        return self


class AskDiaryRequest(DiarySearchFilters):
    query: str | None = Field(default=None, min_length=1, max_length=240)
    run_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def requires_visible_scope(self) -> "AskDiaryRequest":
        if not (
            (self.query and self.query.strip())
            or self.date_from
            or self.date_to
            or self.mood
            or self.media_type
            or self.entry_ids
        ):
            raise ValueError("Ask your diary requires a question or visible filters")
        return self


class SourceCard(BaseModel):
    entry_id: UUID
    local_date: date
    title: str
    excerpt: str | None = None


class AskDiaryResponse(BaseModel):
    answer: str
    source_count: int
    date_from: date
    date_to: date
    sources: list[SourceCard]
    reflection_prompt: str | None = None


class RecapRequest(BaseModel):
    recap_type: Literal["weekly", "monthly", "custom"]
    period_start_date: date
    period_end_date: date
    run_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def valid_period(self) -> "RecapRequest":
        if self.period_start_date > self.period_end_date:
            raise ValueError("period_start_date must be on or before period_end_date")
        return self


class RecapResponse(BaseModel):
    id: UUID | None = None
    recap_type: Literal["weekly", "monthly", "custom"]
    period_start_date: date
    period_end_date: date
    title: str | None = None
    summary: str | None = None
    highlights: list[SourceCard] = Field(default_factory=list)
    source_count: int = 0
    insufficient_material: bool = False
    saved: bool = False
    reflection_prompt: str | None = None


class SaveRecapRequest(BaseModel):
    payload: RecapResponse


class DeviceTokenCreate(BaseModel):
    expo_push_token: str
    platform: Literal["android", "ios"]


class NotificationPreferencesUpdate(BaseModel):
    timezone: str | None = None
    diary_enabled: bool | None = None
    diary_reminder_time: time | None = None
    weekly_recap_enabled: bool | None = None
    weekly_recap_day: int | None = Field(default=None, ge=1, le=7)
    weekly_recap_time: time | None = None


class NotificationPreferencesResponse(BaseModel):
    user_id: UUID
    timezone: str
    diary_enabled: bool
    diary_reminder_time: time | None = None
    weekly_recap_enabled: bool
    weekly_recap_day: int | None = None
    weekly_recap_time: time | None = None


# Compatibility-only contracts below keep deployed legacy rows readable while
# the mobile v1 no longer invokes their routes. They are not used by new flows.
DayFeeling = Literal["loved", "low", "mixed", "quiet"]


class ActivityCreate(BaseModel):
    title: str
    purpose: str | None = None
    start_date: date
    end_date: date | None = None
    cadence_type: Literal["daily", "weekdays"]
    cadence_config: dict = Field(default_factory=dict)
    reminder_time: str | None = None


class ActivityResponse(ActivityCreate):
    id: UUID
    status: str
    streak: int = 0
    current_streak: int = 0
    longest_streak: int = 0
    completed_at: datetime | None = None
    recap_status: str | None = None
    completed_for_date: bool = False
    due_for_date: bool = False


class DiaryEntryUpsert(BaseModel):
    title: str
    body: str
    mood: str | None = None
    day_feeling: DayFeeling | None = None


class AddendumCreate(BaseModel):
    body: str | None = None


class AddendumUpdate(BaseModel):
    body: str | None = Field(default=None, max_length=20_000)


class AddendumResponse(BaseModel):
    id: UUID
    entry_id: UUID
    body: str | None = None
    created_at: datetime
    media: list[EntryMediaResponse] = Field(default_factory=list)


class AttachmentRemovalResponse(BaseModel):
    deleted: bool = True
    addendum_deleted: bool = False


class CaptureCreate(BaseModel):
    initiated_from: Literal["diary", "activity"] = "diary"
    requested_activity_id: UUID | None = None
    raw_text: str | None = None
    local_date: date | None = None
    day_feeling: DayFeeling | None = None


class CaptureResponse(BaseModel):
    id: UUID
    status: str
    local_date: date
    entry_id: UUID | None = None


class UploadUrlRequest(BaseModel):
    media_type: MediaType
    file_extension: str
    content_type: str


UploadUrlResponse = MediaUploadResponse


class DraftResponse(BaseModel):
    id: UUID
    entry_id: UUID
    run_id: str
    payload: dict
    status: str
    version: int


class ActivityReviewDecision(BaseModel):
    action: Literal["accept", "change", "decline"]
    activity_id: UUID | None = None
    milestone: str | None = None
    note: str | None = None


class DraftReview(BaseModel):
    action: Literal["approve", "edit", "discard"]
    entry: DiaryEntryUpsert | None = None
    activity_update: ActivityReviewDecision | None = None

    @model_validator(mode="after")
    def validate_edit(self) -> "DraftReview":
        if self.action == "edit" and self.entry is None:
            raise ValueError("An edit decision needs the edited entry")
        return self


class ReviewResponse(BaseModel):
    status: str
    entry_id: UUID


class CheckinCreate(BaseModel):
    milestone: str
    note: str | None = None
    next_small_step: str | None = None
    local_date: date | None = None


class CheckinResponse(BaseModel):
    id: UUID
    activity_id: UUID
    entry_id: UUID | None = None
    local_date: date
    milestone: str
    note: str | None = None
    next_small_step: str | None = None
    source_badge: str = "user_written"
    audio_count: int = 0
    image_count: int = 0
    status: str


class ActivityEventResponse(BaseModel):
    id: UUID
    activity_id: UUID
    local_date: date
    event_type: str
    checkin_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class ActivityRecapResponse(BaseModel):
    id: UUID
    activity_id: UUID
    payload: dict
    status: str
    created_at: datetime


class ActivitySearchResult(BaseModel):
    activity: ActivityResponse
    matching_checkins: list[CheckinResponse] = Field(default_factory=list)


class ActivityRecapReview(BaseModel):
    action: Literal["approve", "discard"]


class ActivityStatusUpdate(BaseModel):
    status: Literal["active", "paused"]


class TodayResponse(BaseModel):
    local_date: date
    entry: DiaryEntryResponse | None
    activities: list[ActivityResponse]


class ExploreFocusResponse(BaseModel):
    activity: ActivityResponse
    reason: str
    rule: str


class ExploreContinuityResponse(BaseModel):
    activity_id: UUID
    activity_title: str
    checkin_id: UUID
    local_date: date
    next_small_step: str


class AgentInsightResponse(BaseModel):
    id: UUID
    insight_type: str
    body: str
    source_count: int
    date_from: date
    date_to: date


class WeeklyProofResponse(BaseModel):
    recap_id: UUID
    entry_count: int
    checkin_count: int
    return_count: int = 0


class ExploreAskRequest(BaseModel):
    query: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    activity_id: UUID | None = None
    media_type: MediaType | None = None


class ExploreSourceCard(BaseModel):
    source_type: str
    source_id: UUID
    activity_id: UUID | None = None
    local_date: date
    title: str
    excerpt: str | None = None


class ExploreAskResponse(BaseModel):
    answer: str
    source_count: int
    date_from: date
    date_to: date
    sources: list[ExploreSourceCard] = Field(default_factory=list)


class WeeklyRecapResponse(BaseModel):
    id: UUID
    week_start_date: date
    payload: dict
    status: str


class SearchRecapRequest(BaseModel):
    entry_ids: list[UUID]


class SearchRecapHighlightResponse(BaseModel):
    entry_id: UUID
    highlight: str


class SearchRecapResponse(BaseModel):
    summary: str
    result_count: int
    date_from: date
    date_to: date
    highlights: list[SearchRecapHighlightResponse] = Field(default_factory=list)
