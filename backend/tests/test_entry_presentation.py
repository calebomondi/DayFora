from types import SimpleNamespace
from uuid import uuid4

from app.main import enrich_diary_entries, entry_source_badge


def test_entry_source_badge_prefers_user_written_text() -> None:
    assert (
        entry_source_badge({"source_labels": ["user_written", "transcribed", "ai_generated"]})
        == "user_written"
    )


def test_entry_source_badge_marks_media_only_drafts_as_ai() -> None:
    assert entry_source_badge({"source_labels": ["transcribed", "ai_generated"]}) == "ai_generated"


def test_entry_presentation_counts_private_media_and_keeps_one_source_badge() -> None:
    entry_id = str(uuid4())
    audio_id = str(uuid4())
    image_id = str(uuid4())
    client = _PresentationClient(
        {
            "drafts": [{"entry_id": entry_id, "payload": {"source_labels": ["user_written"]}}],
            "entry_media": [
                {"entry_id": entry_id, "media_item_id": audio_id},
                {"entry_id": entry_id, "media_item_id": image_id},
            ],
            "media_items": [
                {"id": audio_id, "media_type": "audio"},
                {"id": image_id, "media_type": "image"},
            ],
            "diary_entry_addenda": [
                {"entry_id": entry_id},
            ],
        }
    )

    entries = enrich_diary_entries(
        [
            {
                "id": entry_id,
                "local_date": "2026-07-18",
                "title": "A quiet win",
                "body": "I kept the original words.",
                "mood": None,
                "day_feeling": "loved",
                "status": "approved",
            }
        ],
        client,  # type: ignore[arg-type]
        "user-001",
    )

    assert entries[0].source_badge == "user_written"
    assert entries[0].audio_count == 1
    assert entries[0].image_count == 1
    assert entries[0].addenda_count == 1
    assert entries[0].day_feeling == "loved"


class _PresentationQuery:
    def __init__(self, data: list[dict]) -> None:
        self._data = data

    def select(self, *_: str) -> "_PresentationQuery":
        return self

    def eq(self, *_: object) -> "_PresentationQuery":
        return self

    def in_(self, *_: object) -> "_PresentationQuery":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self._data)


class _PresentationClient:
    def __init__(self, rows: dict[str, list[dict]]) -> None:
        self.rows = rows

    def table(self, name: str) -> _PresentationQuery:
        return _PresentationQuery(self.rows[name])
