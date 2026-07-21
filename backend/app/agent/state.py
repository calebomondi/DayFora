from typing import Any, Literal, TypedDict


class DiarySourceEntry(TypedDict):
    """The only diary data permitted in an agent graph state."""

    id: str
    local_date: str
    title: str
    body: str | None
    mood: str | None


class DayForaAgentState(TypedDict, total=False):
    """Narrow, request-scoped state for private diary retrieval workflows."""

    run_id: str
    user_id: str
    trigger: Literal["ask_diary", "recap"]
    query: str | None
    period: dict[str, str] | None
    filters: dict[str, Any]
    source_entries: list[DiarySourceEntry]
    result: dict[str, Any] | None
    errors: list[str]
