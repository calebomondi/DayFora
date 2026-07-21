from unittest.mock import patch

from app.agent.memory import synthesize_memory_result


def _state(trigger: str = "ask_diary") -> dict[str, object]:
    return {
        "run_id": "run-fallback",
        "user_id": "user-1",
        "trigger": trigger,
        "query": "What did I save?",
        "source_entries": [
            {
                "id": "entry-1",
                "local_date": "2026-07-20",
                "title": "A quiet morning",
                "body": "I wrote a few words.",
                "mood": "quiet",
            }
        ],
    }


@patch("app.agent.memory.structured_story_answer_model")
def test_memory_synthesis_fallback_is_factual_and_source_linked(model: object) -> None:
    model.return_value.invoke.side_effect = RuntimeError("provider unavailable")  # type: ignore[attr-defined]

    result = synthesize_memory_result(_state())

    assert result["source_entry_ids"] == ["entry-1"]
    assert "A quiet morning" in result["answer"]
    assert "body" not in result["answer"]


@patch("app.agent.memory.structured_diary_recap_model")
def test_recap_fallback_is_not_available_for_single_source(model: object) -> None:
    # The graph enforces the insufficient-material branch before this helper is
    # called; the helper itself remains deterministic for a verified scope.
    model.return_value.invoke.side_effect = RuntimeError("provider unavailable")  # type: ignore[attr-defined]
    result = synthesize_memory_result(_state("recap"))
    assert result["source_entry_ids"] == ["entry-1"]


@patch("app.agent.memory.structured_diary_recap_model")
def test_recap_addresses_reader_and_includes_every_source_entry(model: object) -> None:
    state = _state("recap")
    state["source_entries"] = [
        *state["source_entries"],
        {
            "id": "entry-2",
            "local_date": "2026-07-21",
            "title": "A clearer plan",
            "body": "I chose the next step.",
            "mood": "quiet",
        },
    ]
    model.return_value.invoke.return_value = {
        "title": "The user's week took shape",
        "summary": "The user moved from notes to a clearer plan.",
        "highlights": [{"entry_id": "entry-1", "text": "The user started."}],
        "coverage": {"entry_count": 1, "start_date": "2026-07-20", "end_date": "2026-07-20"},
        "source_entry_ids": ["entry-1"],
        "reflection_prompt": "Revisit this?",
    }

    result = synthesize_memory_result(state)

    assert result["source_entry_ids"] == ["entry-1", "entry-2"]
    assert [item["entry_id"] for item in result["highlights"]] == ["entry-1", "entry-2"]
    assert "the user" not in result["title"].lower()
    assert "the user" not in result["summary"].lower()
    assert result["reflection_prompt"].endswith("?")
