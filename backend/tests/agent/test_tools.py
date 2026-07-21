from __future__ import annotations

from unittest.mock import MagicMock

from app.agent.tools.supabase import SupabaseTools


class TestGetUserPreferences:
    def test_queries_profiles_table(self, tools: SupabaseTools, mock_client: MagicMock) -> None:
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "id": "u1",
            "timezone": "UTC",
        }
        result = tools.get_user_preferences("u1")
        assert result["id"] == "u1"
        mock_client.table.assert_called_with("profiles")


class TestGetMediaForCapture:
    def test_returns_empty_when_no_links(
        self, tools: SupabaseTools, mock_client: MagicMock
    ) -> None:
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        result = tools.get_media_for_capture("cap1", "u1")
        assert result == []

    def test_queries_media_items_for_linked_ids(
        self, tools: SupabaseTools, mock_client: MagicMock
    ) -> None:
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"media_item_id": "m1"},
            {"media_item_id": "m2"},
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
            {"id": "m1", "media_type": "audio", "storage_path": "a.m4a"},
            {"id": "m2", "media_type": "image", "storage_path": "b.jpg"},
        ]
        result = tools.get_media_for_capture("cap1", "u1")
        assert len(result) == 2


class TestDownloadMedia:
    def test_downloads_from_bucket(self, tools: SupabaseTools, mock_client: MagicMock) -> None:
        mock_client.storage.from_.return_value.download.return_value = b"audio-data"
        result = tools.download_media("users/u1/cap1/audio.m4a")
        assert result == b"audio-data"
        mock_client.storage.from_.assert_called_with("dayfora-media")


class TestSetEntryStatus:
    def test_updates_diary_entries(self, tools: SupabaseTools, mock_client: MagicMock) -> None:
        tools.set_entry_status("e1", "u1", "approved")
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.assert_called_once()


class TestSetCaptureStatus:
    def test_updates_captures(self, tools: SupabaseTools, mock_client: MagicMock) -> None:
        tools.set_capture_status("c1", "u1", "processing")
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.assert_called_once()


class TestApproveEntry:
    def test_includes_mood_when_present(self, tools: SupabaseTools, mock_client: MagicMock) -> None:
        tools.approve_entry("e1", "u1", {"title": "T", "body": "B", "mood": "focused"})
        update_call = mock_client.table.return_value.update
        update_call.assert_called_once()
        args = update_call.call_args[0][0]
        assert args["mood"] == "focused"
        assert args["status"] == "approved"

    def test_omits_mood_when_absent(self, tools: SupabaseTools, mock_client: MagicMock) -> None:
        tools.approve_entry("e1", "u1", {"title": "T", "body": "B"})
        args = mock_client.table.return_value.update.call_args[0][0]
        assert "mood" not in args

    def test_includes_user_selected_day_feeling_when_present(
        self, tools: SupabaseTools, mock_client: MagicMock
    ) -> None:
        tools.approve_entry("e1", "u1", {"title": "T", "body": "B", "day_feeling": "mixed"})
        args = mock_client.table.return_value.update.call_args[0][0]
        assert args["day_feeling"] == "mixed"


class TestSaveMediaTranscript:
    def test_updates_transcript_and_status(
        self, tools: SupabaseTools, mock_client: MagicMock
    ) -> None:
        tools.save_media_transcript("m1", "Hello world")
        args = mock_client.table.return_value.update.call_args[0][0]
        assert args["transcript"] == "Hello world"
        assert args["processing_status"] == "complete"


class TestSaveMediaDescription:
    def test_updates_ai_description(self, tools: SupabaseTools, mock_client: MagicMock) -> None:
        desc = {"caption": "A sunset", "objects": [], "context": "evening"}
        tools.save_media_description("m1", desc)
        args = mock_client.table.return_value.update.call_args[0][0]
        assert args["ai_description"]["caption"] == "A sunset"
        assert args["processing_status"] == "complete"


class TestLinkMediaToEntry:
    def test_upserts_entry_media(self, tools: SupabaseTools, mock_client: MagicMock) -> None:
        tools.link_media_to_entry("e1", "m1", "source")
        mock_client.table.return_value.upsert.assert_called_once()
        args = mock_client.table.return_value.upsert.call_args[0][0]
        assert args["entry_id"] == "e1"
        assert args["media_item_id"] == "m1"
        assert args["role"] == "source"


class TestSaveActivityCheckin:
    def test_upserts_checkin(self, tools: SupabaseTools, mock_client: MagicMock) -> None:
        tools.save_activity_checkin("a1", "u1", "e1", "2026-07-18", "Built flow", None)
        mock_client.table.return_value.upsert.assert_called_once()
        args = mock_client.table.return_value.upsert.call_args[0][0]
        assert args["activity_id"] == "a1"
        assert args["milestone"] == "Built flow"
        assert args["status"] == "approved"


class TestGetActivityCheckins:
    def test_queries_checkins(self, tools: SupabaseTools, mock_client: MagicMock) -> None:
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = [
            {"id": "ch1", "milestone": "Built flow", "local_date": "2026-07-18"}
        ]
        result = tools.get_activity_checkins("a1", "u1")
        assert len(result) == 1
        assert result[0]["milestone"] == "Built flow"

    def test_returns_empty_list_when_no_data(
        self, tools: SupabaseTools, mock_client: MagicMock
    ) -> None:
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = None
        result = tools.get_activity_checkins("a1", "u1")
        assert result == []


class TestGetActivity:
    def test_returns_activity(self, tools: SupabaseTools, mock_client: MagicMock) -> None:
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "a1",
            "title": "Build Week",
            "cadence_type": "daily",
        }
        result = tools.get_activity("a1", "u1")
        assert result is not None
        assert result["title"] == "Build Week"

    def test_returns_none_when_not_found(
        self, tools: SupabaseTools, mock_client: MagicMock
    ) -> None:
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
        result = tools.get_activity("nonexistent", "u1")
        assert result is None
