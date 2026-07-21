from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent.graph import build_memory_graph
from app.agent.retrieval import hybrid_entry_score, rank_hybrid_entries
from app.main import (
    _semantic_entry_scores,
    agent_scoped_entries,
    app,
    entry_matches_search_words,
    explicit_entry_mood,
    has_saved_entry_content,
    optional_response_data,
    resolve_saved_direct_entry,
)
from app.schemas import (
    DiaryEntryResponse,
    DiaryEntryWrite,
    DiaryMediaPreview,
    ExploreDiscoveryResponse,
    ExploreMediaItem,
    RecapRequest,
)


def test_direct_entry_requires_body_or_owned_media_reference() -> None:
    with pytest.raises(ValidationError, match="written description, voice note, or photo"):
        DiaryEntryWrite(title="A small day")


def test_direct_entry_accepts_private_media_without_a_body() -> None:
    entry = DiaryEntryWrite(title="A small day", media_item_ids=[uuid4()])
    assert entry.body is None


def test_direct_entry_rejects_more_than_ten_title_words() -> None:
    with pytest.raises(ValidationError, match="at most 10 words"):
        DiaryEntryWrite(
            title="one two three four five six seven eight nine ten eleven", body="Saved"
        )


def test_recap_period_cannot_be_reversed() -> None:
    with pytest.raises(ValidationError, match="on or before"):
        RecapRequest(
            recap_type="weekly",
            period_start_date=date(2026, 7, 20),
            period_end_date=date(2026, 7, 19),
        )


def test_memory_graph_only_accepts_returned_source_ids_from_supplied_scope() -> None:
    graph = build_memory_graph(
        lambda _state: {"answer": "Only this", "source_entry_ids": ["entry-1"]}
    )
    output = graph.invoke(
        {
            "run_id": "run-1",
            "user_id": "user-1",
            "trigger": "ask_diary",
            "query": "What did I save?",
            "source_entries": [
                {
                    "id": "entry-1",
                    "local_date": "2026-07-21",
                    "title": "Saved",
                    "body": None,
                    "mood": None,
                }
            ],
        }
    )
    assert output.get("errors") is None


def test_discovery_contract_is_diary_only() -> None:
    payload = ExploreDiscoveryResponse()
    assert payload.on_this_day == []
    assert payload.saved_recaps == []
    assert payload.saved_entries == []
    assert payload.recent_photos == []
    assert payload.recent_audio == []


def test_discovery_media_item_is_source_linked() -> None:
    item = ExploreMediaItem(
        entry_id=uuid4(),
        media_item_id=uuid4(),
        title="A small day",
        local_date=date(2026, 7, 21),
        signed_url="https://private.example/signed",
    )
    assert item.title == "A small day"


def test_diary_entry_previews_are_private_signed_media_contracts() -> None:
    preview = DiaryMediaPreview(
        id=uuid4(), media_type="image", signed_url="https://private.example/signed"
    )
    entry = DiaryEntryResponse(
        id=uuid4(),
        local_date=date(2026, 7, 21),
        title="A small day",
        preview_images=[preview],
    )
    assert entry.preview_images[0].signed_url == "https://private.example/signed"
    assert entry.preview_audio is None


def test_retired_memories_path_redirects_to_explore_discovery() -> None:
    response = TestClient(app).get("/v1/memories", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/v1/explore/discover"


def test_direct_save_rereads_the_owned_entry_when_postgrest_returns_no_representation() -> None:
    class Query:
        def select(self, *_: object) -> "Query":
            return self

        def eq(self, *_: object) -> "Query":
            return self

        def maybe_single(self) -> "Query":
            return self

        def execute(self) -> object:
            return type("Response", (), {"data": {"id": "entry-1", "title": "Saved"}})()

    class Client:
        def table(self, _: str) -> Query:
            return Query()

    saved = resolve_saved_direct_entry(Client(), None, "user-1", date(2026, 7, 21))
    assert saved["id"] == "entry-1"


def test_empty_maybe_single_response_is_a_missing_entry_not_a_server_error() -> None:
    assert optional_response_data(None) is None


def test_removing_an_attachment_cannot_leave_a_diary_record_title_only() -> None:
    assert not has_saved_entry_content(None, 0)
    assert has_saved_entry_content("A written memory", 0)
    assert has_saved_entry_content(None, 1)


def test_empty_addendum_is_identified_after_its_last_attachment_is_removed() -> None:
    assert not has_saved_entry_content("", 0)
    assert has_saved_entry_content("A later thought", 0)


def test_visible_search_matches_titles_but_not_entry_bodies() -> None:
    entry = {"title": "A quiet afternoon", "body": "I mentioned the library here."}
    assert entry_matches_search_words(entry, ["quiet"], title_only=True)
    assert not entry_matches_search_words(entry, ["library"], title_only=True)
    assert entry_matches_search_words(entry, ["library"], title_only=False)


def test_hybrid_search_ignores_question_framing_and_matches_close_terms() -> None:
    entries = [
        {
            "id": "buildathon",
            "title": "OpenAI Buildathon",
            "body": "I tested the memory guide with a small source set.",
        },
        {"id": "walk", "title": "Quiet walk", "body": "A slow afternoon outside."},
    ]
    ranked = rank_hybrid_entries(entries, "What happened in openai hackathon?")
    assert [entry["id"] for entry in ranked] == ["buildathon"]
    assert hybrid_entry_score(entries[0], "What happened in openai hackathon?") > 0.4


def test_hybrid_title_search_does_not_use_body_terms() -> None:
    entry = {"id": "one", "title": "A quiet afternoon", "body": "OpenAI Buildathon notes."}
    assert rank_hybrid_entries([entry], "buildathon", title_only=True) == []
    assert rank_hybrid_entries([entry], "buildathon", title_only=False) == [entry]


def test_hybrid_search_does_not_expand_a_stopword_only_question_to_all_entries() -> None:
    entry = {"id": "one", "title": "A saved day", "body": "Words."}
    assert rank_hybrid_entries([entry], "what is", title_only=False) == []


def test_optional_semantic_scores_are_owner_scoped_and_fail_closed() -> None:
    client = MagicMock()
    client.functions.invoke.return_value = {"embedding": [0.1] * 384}
    client.rpc.return_value.execute.return_value.data = [
        {"entry_id": "entry-1", "similarity": 0.81}
    ]
    with patch.dict("os.environ", {"DAYFORA_SEMANTIC_SEARCH": "true"}, clear=False):
        scores = _semantic_entry_scores(client, "user-1", "buildathon")
    assert scores == {"entry-1": 0.81}
    rpc_args = client.rpc.call_args.args
    assert rpc_args[0] == "match_diary_entry_embeddings"
    assert rpc_args[1]["requested_user_id"] == "user-1"


def test_search_mood_accepts_retained_legacy_rows() -> None:
    assert explicit_entry_mood({"mood_v1": "mixed", "mood": "happy_fun"}) == "mixed"
    assert explicit_entry_mood({"mood": "mixed"}) == "mixed"


def test_agent_scope_contains_no_media_or_processing_fields() -> None:
    scoped = agent_scoped_entries(
        [
            {
                "id": "entry-1",
                "local_date": "2026-07-21",
                "title": "A saved day",
                "body": "Words",
                "mood_v1": "mixed",
                "storage_path": "users/user-1/private.m4a",
                "signed_url": "https://private.example/no",
            }
        ]
    )
    assert scoped == [
        {
            "id": "entry-1",
            "local_date": "2026-07-21",
            "title": "A saved day",
            "body": "Words",
            "mood": "mixed",
        }
    ]
