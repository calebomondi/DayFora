from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from supabase_auth.errors import AuthApiError

from app.main import activity_is_due_for_date, app

FAKE_TOKEN = "Bearer test-token-123"
UUID1 = str(uuid4())
UUID2 = str(uuid4())
UUID3 = str(uuid4())
UUID4 = str(uuid4())
UUID5 = str(uuid4())


def _auth_headers() -> dict[str, str]:
    return {"Authorization": FAKE_TOKEN}


def _mock_user(user_id: str = "user-001") -> MagicMock:
    user = MagicMock()
    user.id = user_id
    return user


class TestHealthEndpoint:
    def test_health_returns_ok(self) -> None:
        response = TestClient(app).get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestAuthGuard:
    def test_requires_bearer_token(self) -> None:
        response = TestClient(app).get("/v1/today")
        assert response.status_code == 401

    def test_rejects_invalid_token(self) -> None:
        with patch("app.main.anon_client") as mock_anon:
            mock_anon.return_value.auth.get_user.return_value = MagicMock(user=None)
            response = TestClient(app).get("/v1/today", headers=_auth_headers())
            assert response.status_code == 401

    def test_rejects_deleted_user_token_without_an_internal_server_error(self) -> None:
        with patch("app.main.anon_client") as mock_anon:
            mock_anon.return_value.auth.get_user.side_effect = AuthApiError(
                "User from sub claim in JWT does not exist",
                403,
                "user_not_found",
            )

            response = TestClient(app).get("/v1/today", headers=_auth_headers())

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired bearer token"


class TestCaptureProcessingEvents:
    @patch("app.main.anon_client")
    @patch("app.main._process_capture")
    def test_streams_safe_capture_progress_and_completion(
        self, mock_process: MagicMock, mock_anon: MagicMock
    ) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())

        def process(_capture_id: str, _user_id: str, report_progress: object) -> dict[str, str]:
            assert callable(report_progress)
            report_progress("transcribing_audio", "Transcribing your recording")
            return {
                "id": UUID1,
                "status": "approved",
                "local_date": "2026-07-20",
                "entry_id": UUID2,
            }

        mock_process.side_effect = process

        response = TestClient(app).post(
            f"/v1/captures/{UUID1}/process/events", headers=_auth_headers()
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: progress" in response.text
        assert "Transcribing your recording" in response.text
        assert "event: complete" in response.text


class TestProfile:
    @patch("app.main.anon_client")
    def test_reads_onboarding_completion_for_the_authenticated_user(
        self, mock_anon: MagicMock
    ) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            query = mock_svc.return_value.table.return_value.select.return_value.eq.return_value
            query.maybe_single.return_value.execute.return_value.data = {
                "onboarding_completed_at": "2026-07-18T10:30:00+00:00",
                "created_at": "2026-07-18T09:00:00+00:00",
            }

            response = TestClient(app).get("/v1/profile", headers=_auth_headers())

        assert response.status_code == 200
        assert response.json()["onboarding_completed_at"] == "2026-07-18T10:30:00Z"
        assert response.json()["created_at"] == "2026-07-18T09:00:00Z"
        mock_svc.return_value.table.return_value.select.return_value.eq.assert_called_once_with(
            "id", "user-001"
        )

    @patch("app.main.anon_client")
    def test_persists_onboarding_completion_for_the_authenticated_user(
        self, mock_anon: MagicMock
    ) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            update = mock_svc.return_value.table.return_value.update.return_value.eq.return_value
            update.execute.return_value.data = [
                {"onboarding_completed_at": "2026-07-18T10:30:00+00:00"}
            ]

            response = TestClient(app).post(
                "/v1/profile/onboarding-complete", headers=_auth_headers()
            )

        assert response.status_code == 200
        assert response.json()["onboarding_completed_at"] == "2026-07-18T10:30:00Z"
        mock_svc.return_value.table.return_value.update.return_value.eq.assert_called_once_with(
            "id", "user-001"
        )


class TestActivityDueDate:
    def test_only_active_eligible_cadences_are_due(self) -> None:
        weekday = {"status": "active", "start_date": "2026-07-13", "cadence_type": "weekdays"}
        weekly = {"status": "active", "start_date": "2026-07-14", "cadence_type": "weekly"}

        assert activity_is_due_for_date(weekday, date(2026, 7, 17))
        assert not activity_is_due_for_date(weekday, date(2026, 7, 18))
        assert not activity_is_due_for_date(weekly, date(2026, 7, 21))
        assert not activity_is_due_for_date(weekly, date(2026, 7, 22))


class TestActivityRecap:
    @patch("app.main.anon_client")
    def test_returns_null_when_an_activity_has_no_proof_recap(self, mock_anon: MagicMock) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            query = mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single
            query.return_value.execute.return_value = None

            response = TestClient(app).get(f"/v1/activities/{UUID1}/recap", headers=_auth_headers())

        assert response.status_code == 200
        assert response.json() is None


class TestListDiaryEntries:
    @patch("app.main.anon_client")
    def test_returns_only_the_authenticated_users_approved_entries(
        self, mock_anon: MagicMock
    ) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            query = mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value
            query.order.return_value.limit.return_value.execute.return_value.data = [
                {
                    "id": UUID1,
                    "user_id": "user-001",
                    "local_date": "2026-07-18",
                    "title": "A quiet win",
                    "body": "I finished the Library view.",
                    "mood": "focused",
                    "status": "approved",
                }
            ]

            response = TestClient(app).get("/v1/entries?limit=20", headers=_auth_headers())

        assert response.status_code == 200
        assert response.json()[0]["title"] == "A quiet win"
        mock_svc.return_value.table.return_value.select.return_value.eq.assert_any_call(
            "user_id", "user-001"
        )
        mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.assert_called_once_with(
            "status", "approved"
        )

    @patch("app.main.anon_client")
    def test_rejects_an_unbounded_page_size(self, mock_anon: MagicMock) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        response = TestClient(app).get("/v1/entries?limit=101", headers=_auth_headers())

        assert response.status_code == 422


class TestEntryMedia:
    @patch("app.main.anon_client")
    def test_returns_only_owned_private_media_with_temporary_urls(
        self, mock_anon: MagicMock
    ) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        media_client = _EntryMediaClient(
            {
                "diary_entries": {"id": UUID2},
                "entry_media": [
                    {"media_item_id": UUID3},
                    {"media_item_id": UUID4},
                ],
                "media_items": [
                    {
                        "id": UUID3,
                        "media_type": "audio",
                        "storage_path": "users/user-001/captures/audio.m4a",
                        "transcript": "I kept going.",
                        "ai_description": None,
                    },
                    {
                        "id": UUID4,
                        "media_type": "image",
                        "storage_path": "users/user-001/captures/image.jpg",
                        "transcript": None,
                        "ai_description": {"caption": "A notebook."},
                    },
                ],
            }
        )
        media_client.storage.from_.return_value.create_signed_url.side_effect = [
            {"signedUrl": "https://storage.example/audio"},
            {"signedUrl": "https://storage.example/image"},
        ]
        with patch("app.main.service_client", return_value=media_client):
            response = TestClient(app).get(f"/v1/entries/{UUID2}/media", headers=_auth_headers())

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": UUID3,
                "media_type": "audio",
                "signed_url": "https://storage.example/audio",
                "transcript": None,
                "ai_description": None,
            },
            {
                "id": UUID4,
                "media_type": "image",
                "signed_url": "https://storage.example/image",
                "transcript": None,
                "ai_description": None,
            },
        ]
        media_client.storage.from_.return_value.create_signed_url.assert_any_call(
            "users/user-001/captures/audio.m4a", 900
        )

    @patch("app.main.anon_client")
    def test_hides_media_when_the_entry_is_not_owned(self, mock_anon: MagicMock) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        media_client = _EntryMediaClient({"diary_entries": None})
        with patch("app.main.service_client", return_value=media_client):
            response = TestClient(app).get(f"/v1/entries/{UUID2}/media", headers=_auth_headers())

        assert response.status_code == 404
        media_client.storage.from_.assert_not_called()


class TestDiaryAddenda:
    @patch("app.main.local_today", return_value=date(2026, 7, 19))
    @patch("app.main.anon_client")
    def test_appends_to_a_past_owned_entry_only(
        self, mock_anon: MagicMock, _mock_today: MagicMock
    ) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            entry_query = mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single
            entry_query.return_value.execute.return_value.data = {
                "id": UUID2,
                "local_date": "2026-07-18",
            }
            mock_svc.return_value.table.return_value.insert.return_value.execute.return_value.data = [
                {
                    "id": UUID3,
                    "entry_id": UUID2,
                    "body": "A quieter ending helped.",
                    "created_at": "2026-07-19T08:00:00+00:00",
                }
            ]

            response = TestClient(app).post(
                f"/v1/entries/{UUID2}/addenda",
                json={"body": "A quieter ending helped."},
                headers=_auth_headers(),
            )

        assert response.status_code == 201
        assert response.json()["body"] == "A quieter ending helped."

    @patch("app.main.local_today", return_value=date(2026, 7, 19))
    @patch("app.main.anon_client")
    def test_rejects_rewriting_today_through_addenda(
        self, mock_anon: MagicMock, _mock_today: MagicMock
    ) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            entry_query = mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single
            entry_query.return_value.execute.return_value.data = {
                "id": UUID2,
                "local_date": "2026-07-19",
            }

            response = TestClient(app).post(
                f"/v1/entries/{UUID2}/addenda",
                json={"body": "This should be an edit."},
                headers=_auth_headers(),
            )

        assert response.status_code == 409


class TestDiarySearch:
    @patch("app.main.anon_client")
    def test_searches_only_approved_owned_title_and_body_content(
        self, mock_anon: MagicMock
    ) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        client = _EntryMediaClient(
            {
                "diary_entries": [
                    {
                        "id": UUID2,
                        "user_id": "user-001",
                        "local_date": "2026-07-18",
                        "title": "Authentication progress",
                        "body": "The session flow is clear now.",
                        "mood": None,
                        "status": "approved",
                    },
                    {
                        "id": UUID3,
                        "user_id": "user-001",
                        "local_date": "2026-07-17",
                        "title": "A quiet walk",
                        "body": "No code today.",
                        "mood": None,
                        "status": "approved",
                    },
                ],
                "drafts": [],
                "entry_media": [],
                "media_items": [],
                "diary_entry_addenda": [],
            }
        )
        with patch("app.main.service_client", return_value=client):
            response = TestClient(app).get(
                "/v1/diary/search?query=session", headers=_auth_headers()
            )

        assert response.status_code == 200
        assert [entry["id"] for entry in response.json()] == [UUID2]

    @patch("app.main.structured_search_recap_model")
    @patch("app.main.anon_client")
    def test_search_recap_uses_only_verified_requested_entries(
        self, mock_anon: MagicMock, mock_model: MagicMock
    ) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        client = _EntryMediaClient(
            {
                "diary_entries": [
                    {
                        "id": UUID2,
                        "local_date": "2026-07-18",
                        "title": "A quiet win",
                        "body": "I finished the search flow.",
                    }
                ]
            }
        )
        mock_model.return_value.invoke.return_value.model_dump.return_value = {
            "summary": "You made steady room for the search flow.",
            "highlights": [{"entry_id": UUID2, "highlight": "The search flow became clear."}],
        }
        with patch("app.main.service_client", return_value=client):
            response = TestClient(app).post(
                "/v1/diary/search-recap",
                json={"entry_ids": [UUID2]},
                headers=_auth_headers(),
            )

        assert response.status_code == 200
        assert response.json()["result_count"] == 1
        assert response.json()["highlights"][0]["entry_id"] == UUID2


class _EntryMediaQuery:
    def __init__(self, data: object) -> None:
        self._data = data

    def select(self, *_: object) -> "_EntryMediaQuery":
        return self

    def eq(self, *_: object) -> "_EntryMediaQuery":
        return self

    def in_(self, *_: object) -> "_EntryMediaQuery":
        return self

    def gte(self, *_: object) -> "_EntryMediaQuery":
        return self

    def lte(self, *_: object) -> "_EntryMediaQuery":
        return self

    def order(self, *_: object, **__: object) -> "_EntryMediaQuery":
        return self

    def limit(self, *_: object) -> "_EntryMediaQuery":
        return self

    def maybe_single(self) -> "_EntryMediaQuery":
        return self

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self._data)


class _EntryMediaClient:
    def __init__(self, tables: dict[str, object]) -> None:
        self.tables = tables
        self.storage = MagicMock()

    def table(self, name: str) -> _EntryMediaQuery:
        return _EntryMediaQuery(self.tables.get(name, []))


class TestCreateCapture:
    @patch("app.main.anon_client")
    def test_creates_text_capture(self, mock_anon: MagicMock) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            mock_svc.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                "timezone": "UTC",
            }
            mock_svc.return_value.table.return_value.insert.return_value.execute.return_value.data = [
                {"id": UUID1, "status": "uploaded", "local_date": "2026-07-18"},
            ]
            response = TestClient(app).post(
                "/v1/captures",
                json={"raw_text": "Hello world"},
                headers=_auth_headers(),
            )
            assert response.status_code == 201
            assert response.json()["id"] == UUID1

    @patch("app.main.anon_client")
    @patch("app.main.local_today", return_value=date(2026, 7, 18))
    def test_allows_an_explicit_past_capture_date(
        self, _mock_local_today: MagicMock, mock_anon: MagicMock
    ) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            mock_svc.return_value.table.return_value.insert.return_value.execute.return_value.data = [
                {"id": UUID1, "status": "uploaded", "local_date": "2026-07-17"},
            ]
            response = TestClient(app).post(
                "/v1/captures",
                json={"raw_text": "A belated reflection", "local_date": "2026-07-17"},
                headers=_auth_headers(),
            )

            assert response.status_code == 201
            inserted = mock_svc.return_value.table.return_value.insert.call_args.args[0]
            assert inserted["local_date"] == "2026-07-17"
            assert inserted["raw_text"] == "A belated reflection"

    @patch("app.main.anon_client")
    @patch("app.main.local_today", return_value=date(2026, 7, 18))
    def test_rejects_a_future_capture_date(
        self, _mock_local_today: MagicMock, mock_anon: MagicMock
    ) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        response = TestClient(app).post(
            "/v1/captures",
            json={"raw_text": "Tomorrow", "local_date": "2026-07-19"},
            headers=_auth_headers(),
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "A capture cannot be created for a future day"

    @patch("app.main.anon_client")
    def test_rejects_invalid_activity_id(self, mock_anon: MagicMock) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            mock_svc.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
                "timezone": "UTC",
            }
            mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
            response = TestClient(app).post(
                "/v1/captures",
                json={"requested_activity_id": str(uuid4())},
                headers=_auth_headers(),
            )
            assert response.status_code == 404


class TestGetDraft:
    @patch("app.main.anon_client")
    def test_returns_404_when_no_draft(self, mock_anon: MagicMock) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
            response = TestClient(app).get(
                f"/v1/entries/{UUID2}/draft",
                headers=_auth_headers(),
            )
            assert response.status_code == 404

    @patch("app.main.anon_client")
    def test_returns_draft_when_found(self, mock_anon: MagicMock) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
                "id": UUID3,
                "entry_id": UUID2,
                "run_id": "capture:cap-1",
                "payload": {"title": "T", "body": "B"},
                "status": "ready_for_review",
                "version": 1,
            }
            response = TestClient(app).get(
                f"/v1/entries/{UUID2}/draft",
                headers=_auth_headers(),
            )
            assert response.status_code == 200
            assert response.json()["id"] == UUID3


class TestReviewDraft:
    @patch("app.main.anon_client")
    def test_returns_404_when_draft_not_found(self, mock_anon: MagicMock) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
            response = TestClient(app).post(
                f"/v1/drafts/{UUID4}/review",
                json={"action": "approve"},
                headers=_auth_headers(),
            )
            assert response.status_code == 404

    @patch("app.main.anon_client")
    def test_returns_409_when_draft_not_reviewable(self, mock_anon: MagicMock) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
                "id": UUID4,
                "entry_id": UUID2,
                "status": "approved",
            }
            response = TestClient(app).post(
                f"/v1/drafts/{UUID4}/review",
                json={"action": "approve"},
                headers=_auth_headers(),
            )
            assert response.status_code == 409

    @patch("app.main.build_graph")
    @patch("app.main.anon_client")
    def test_approve_resumes_graph(self, mock_anon: MagicMock, mock_build: MagicMock) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
                "id": UUID4,
                "entry_id": UUID2,
                "status": "ready_for_review",
            }
            mock_build.return_value.invoke.return_value = {}
            response = TestClient(app).post(
                f"/v1/drafts/{UUID4}/review",
                json={"action": "approve"},
                headers=_auth_headers(),
            )
            assert response.status_code == 200
            assert response.json()["status"] == "approved"
            assert response.json()["entry_id"] == UUID2

    @patch("app.main.build_graph")
    @patch("app.main.anon_client")
    def test_discard_resumes_graph(self, mock_anon: MagicMock, mock_build: MagicMock) -> None:
        mock_anon.return_value.auth.get_user.return_value = MagicMock(user=_mock_user())
        with patch("app.main.service_client") as mock_svc:
            mock_svc.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
                "id": UUID5,
                "entry_id": UUID2,
                "status": "ready_for_review",
            }
            mock_build.return_value.invoke.return_value = {}
            response = TestClient(app).post(
                f"/v1/drafts/{UUID5}/review",
                json={"action": "discard"},
                headers=_auth_headers(),
            )
            assert response.status_code == 200
            assert response.json()["status"] == "discarded"
