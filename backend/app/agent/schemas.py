from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MemoryCoverage(BaseModel):
    """The verified part of a diary returned to a memory workflow."""

    entry_count: int = Field(ge=1, le=20)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "MemoryCoverage":
        if self.start_date > self.end_date:
            raise ValueError("coverage start_date must be on or before end_date")
        return self


class DiaryStoryAnswer(BaseModel):
    """Structured, temporary output for an explicit Ask-your-diary request."""

    answer: str = Field(min_length=1, max_length=1_200)
    coverage: MemoryCoverage
    source_entry_ids: list[str] = Field(min_length=1, max_length=20)
    reflection_prompt: str | None = Field(default=None, max_length=280)


class DiaryRecapHighlight(BaseModel):
    entry_id: str
    text: str = Field(min_length=1, max_length=420)


class DiaryRecapOutput(BaseModel):
    """Structured, temporary output for an explicit recap request."""

    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1_400)
    highlights: list[DiaryRecapHighlight] = Field(default_factory=list, max_length=20)
    coverage: MemoryCoverage
    source_entry_ids: list[str] = Field(min_length=1, max_length=20)
    reflection_prompt: str | None = Field(default=None, max_length=280)


class ActivitySuggestion(BaseModel):
    activity_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    milestone: str | None = None
    reason: str | None = None


class ImageDescription(BaseModel):
    caption: str
    objects: list[str] = Field(default_factory=list)
    context: str = ""


class DraftOutput(BaseModel):
    title: str
    body: str
    mood: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_labels: list[Literal["user_written", "transcribed", "ai_generated"]]
    proposed_activity_update: ActivitySuggestion | None = None
    reflection_prompt: str | None = None


class SearchRecapHighlight(BaseModel):
    entry_id: str
    highlight: str


class SearchRecapOutput(BaseModel):
    summary: str
    highlights: list[SearchRecapHighlight] = Field(default_factory=list)


class ActivityRecapOutput(BaseModel):
    title: str
    summary: str
    highlights: list[str] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    action: Literal["approve", "edit", "discard"]
    entry: dict[str, str] | None = None
    activity_update: dict[str, str | None] | None = None
