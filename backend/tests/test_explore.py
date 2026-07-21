from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import (
    _active_insight,
    app,
    choose_focus_candidate,
    is_current_explore_date,
    optional_response_data,
)

FAKE_TOKEN = "Bearer explore-test-token"


def _headers() -> dict[str, str]:
    return {"Authorization": FAKE_TOKEN}


def _user() -> MagicMock:
    user = MagicMock()
    user.id = "user-001"
    return user


def test_focus_priority_prefers_a_saved_smallest_next_step() -> None:
    newest_due = {"id": "recent"}
    chosen = choose_focus_candidate(
        [
            (3, "recent_activity", newest_due, None, "recent"),
            (0, "smallest_next_step", {"id": "step"}, None, "step"),
            (1, "nearing_end_date", {"id": "ending"}, None, "ending"),
        ]
    )

    assert chosen[1] == "smallest_next_step"
    assert chosen[2]["id"] == "step"


def test_insight_is_suppressed_when_fewer_than_three_approved_sources_exist() -> None:
    client = _InsightClient(
        [
            {
                "id": str(uuid4()),
                "insight_type": "pattern",
                "body": "Two moments are not enough evidence.",
                "source_refs": {"entry_ids": [str(uuid4()), str(uuid4())]},
            }
        ]
    )

    assert _active_insight(client, "user-001") is None  # type: ignore[arg-type]


def test_historical_explore_never_uses_current_day_agent_surfaces() -> None:
    assert not is_current_explore_date(date(2026, 7, 19), date(2026, 7, 20))
    assert is_current_explore_date(date(2026, 7, 20), date(2026, 7, 20))


def test_optional_supabase_single_result_is_null_safe() -> None:
    assert optional_response_data(None) is None
    assert optional_response_data(SimpleNamespace(data={"id": "entry-1"})) == {"id": "entry-1"}


@patch("app.main.anon_client")
@patch("app.main.service_client")
def test_dismissal_is_scoped_to_the_authenticated_owner(
    mock_service: MagicMock, mock_anon: MagicMock
) -> None:
    mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_user())
    query = mock_service.return_value.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value
    query.execute.return_value.data = [{"id": str(uuid4())}]

    response = TestClient(app).post(f"/v1/agent-insights/{uuid4()}/dismiss", headers=_headers())

    assert response.status_code == 200
    assert response.json() == {"status": "dismissed"}
    assert "user-001" in str(mock_service.mock_calls)


@patch("app.main.anon_client")
@patch("app.main.service_client")
def test_ask_your_diary_rejects_an_empty_request_scope(
    mock_service: MagicMock, mock_anon: MagicMock
) -> None:
    mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_user())
    response = TestClient(app).post(
        "/v1/explore/ask",
        headers=_headers(),
        json={},
    )

    assert response.status_code == 422


class _InsightQuery:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def select(self, *_: object) -> "_InsightQuery":
        return self

    def eq(self, *_: object) -> "_InsightQuery":
        return self

    def order(self, *_: object, **__: object) -> "_InsightQuery":
        return self

    def limit(self, *_: object) -> "_InsightQuery":
        return self

    def in_(self, *_: object) -> "_InsightQuery":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self.rows)


class _InsightClient:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def table(self, _: str) -> _InsightQuery:
        return _InsightQuery(self.rows)
