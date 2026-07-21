from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import build_memory_graph


def test_memory_graph_rejects_unscoped_sources() -> None:
    graph = build_memory_graph(lambda _state: {})
    output = graph.invoke(
        {
            "run_id": "run-empty",
            "user_id": "user-1",
            "trigger": "ask_diary",
            "query": "What did I save?",
            "source_entries": [],
        }
    )
    assert output["errors"] == ["No verified source entries"]


def test_memory_graph_rejects_sources_the_model_did_not_receive() -> None:
    graph = build_memory_graph(
        lambda _state: {"answer": "Nope", "source_entry_ids": ["outside"]},
        checkpointer=MemorySaver(),
    )
    output = graph.invoke(
        {
            "run_id": "run-1",
            "user_id": "user-1",
            "trigger": "ask_diary",
            "query": "What did I save?",
            "source_entries": [
                {
                    "id": "inside",
                    "local_date": "2026-07-21",
                    "title": "A note",
                    "body": "Words",
                    "mood": None,
                }
            ],
        },
        {"configurable": {"thread_id": "ask:user:run-1"}},
    )
    assert output["errors"] == ["Agent returned an unverified source"]


def test_memory_graph_rejects_media_or_signed_url_fields() -> None:
    graph = build_memory_graph(lambda _state: {})
    output = graph.invoke(
        {
            "run_id": "run-media",
            "user_id": "user-1",
            "trigger": "ask_diary",
            "query": "What did I save?",
            "source_entries": [
                {
                    "id": "entry-1",
                    "local_date": "2026-07-21",
                    "title": "Saved",
                    "body": "Words",
                    "mood": None,
                    "signed_url": "https://private.example/should-not-enter",
                }
            ],
        }
    )
    assert output["errors"] == ["Invalid diary source scope"]


def test_recap_graph_returns_typed_insufficient_material() -> None:
    graph = build_memory_graph(lambda _state: {})
    output = graph.invoke(
        {
            "run_id": "run-recap",
            "user_id": "user-1",
            "trigger": "recap",
            "period": {"start": "2026-07-20", "end": "2026-07-21"},
            "source_entries": [
                {
                    "id": "entry-1",
                    "local_date": "2026-07-21",
                    "title": "Saved",
                    "body": "Words",
                    "mood": None,
                }
            ],
        }
    )
    assert output["result"] == {"status": "insufficient_material"}
