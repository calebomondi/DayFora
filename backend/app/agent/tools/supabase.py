from typing import Any

from supabase import Client

from app.agent.streak import calculate_longest_streak, calculate_streak


class SupabaseTools:
    def __init__(self, client: Client) -> None:
        self.client = client

    # -- Read helpers ----------------------------------------------------------

    def get_user_preferences(self, user_id: str) -> dict[str, Any]:
        return self.client.table("profiles").select("*").eq("id", user_id).single().execute().data

    def get_active_activities(self, user_id: str, local_date: str) -> list[dict[str, Any]]:
        return (
            self.client.table("activities")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
            .data
        )

    def get_capture(self, capture_id: str, user_id: str) -> dict[str, Any]:
        return (
            self.client.table("captures")
            .select("*")
            .eq("id", capture_id)
            .eq("user_id", user_id)
            .single()
            .execute()
            .data
        )

    def get_media_for_capture(self, capture_id: str, user_id: str) -> list[dict[str, Any]]:
        links = (
            self.client.table("capture_media")
            .select("media_item_id")
            .eq("capture_id", capture_id)
            .execute()
            .data
        )
        if not links:
            return []
        ids = [link["media_item_id"] for link in links]
        return (
            self.client.table("media_items")
            .select("*")
            .eq("user_id", user_id)
            .in_("id", ids)
            .execute()
            .data
        )

    def download_media(self, storage_path: str) -> bytes:
        return self.client.storage.from_("dayfora-media").download(storage_path)

    # -- Write helpers ---------------------------------------------------------

    def set_entry_status(self, entry_id: str, user_id: str, status: str) -> None:
        self.client.table("diary_entries").update({"status": status}).eq("id", entry_id).eq(
            "user_id", user_id
        ).execute()

    def set_capture_status(self, capture_id: str, user_id: str, status: str) -> None:
        self.client.table("captures").update({"status": status}).eq("id", capture_id).eq(
            "user_id", user_id
        ).execute()

    def upsert_draft(
        self, entry_id: str, user_id: str, run_id: str, payload: dict[str, Any]
    ) -> None:
        self.client.table("drafts").upsert(
            {
                "entry_id": entry_id,
                "user_id": user_id,
                "run_id": run_id,
                "payload": payload,
                "agent_version": "m4",
                "version": 1,
                "status": "ready_for_review",
            },
            on_conflict="run_id",
        ).execute()

    def approve_entry(self, entry_id: str, user_id: str, entry: dict[str, Any]) -> None:
        update: dict[str, Any] = {
            "title": entry.get("title", ""),
            "body": entry.get("body", ""),
            "status": "approved",
        }
        if entry.get("mood"):
            update["mood"] = entry["mood"]
        if entry.get("day_feeling"):
            update["day_feeling"] = entry["day_feeling"]
        self.client.table("diary_entries").update(update).eq("id", entry_id).eq(
            "user_id", user_id
        ).execute()

    def set_draft_status(self, run_id: str, user_id: str, status: str) -> None:
        self.client.table("drafts").update({"status": status}).eq("run_id", run_id).eq(
            "user_id", user_id
        ).execute()

    def save_media_transcript(self, media_item_id: str, transcript: str) -> None:
        self.client.table("media_items").update(
            {"transcript": transcript, "processing_status": "complete"}
        ).eq("id", media_item_id).execute()

    def set_media_processing_status(self, media_item_id: str, processing_status: str) -> None:
        self.client.table("media_items").update({"processing_status": processing_status}).eq(
            "id", media_item_id
        ).execute()

    def save_media_description(self, media_item_id: str, description: dict[str, Any]) -> None:
        self.client.table("media_items").update(
            {"ai_description": description, "processing_status": "complete"}
        ).eq("id", media_item_id).execute()

    def link_media_to_entry(self, entry_id: str, media_item_id: str, role: str = "source") -> None:
        self.client.table("entry_media").upsert(
            {"entry_id": entry_id, "media_item_id": media_item_id, "role": role},
            on_conflict="entry_id,media_item_id",
        ).execute()

    def save_activity_checkin(
        self,
        activity_id: str,
        user_id: str,
        entry_id: str,
        local_date: str,
        milestone: str,
        note: str | None,
    ) -> str | None:
        result = (
            self.client.table("activity_checkins")
            .upsert(
                {
                    "activity_id": activity_id,
                    "user_id": user_id,
                    "entry_id": entry_id,
                    "local_date": local_date,
                    "milestone": milestone,
                    "note": note,
                    "status": "approved",
                },
                on_conflict="activity_id,local_date",
            )
            .execute()
        )
        checkin = (result.data or [{}])[0]
        if isinstance(checkin.get("id"), str):
            self.client.table("activity_events").upsert(
                {
                    "activity_id": activity_id,
                    "user_id": user_id,
                    "local_date": local_date,
                    "event_type": "checkin",
                    "checkin_id": checkin["id"],
                },
                on_conflict="activity_id,local_date,event_type",
            ).execute()
        return checkin["id"] if isinstance(checkin.get("id"), str) else None

    def link_media_to_checkin(self, checkin_id: str, media_item_id: str) -> None:
        self.client.table("checkin_media").upsert(
            {"checkin_id": checkin_id, "media_item_id": media_item_id},
            on_conflict="checkin_id,media_item_id",
        ).execute()

    def get_activity_checkins(self, activity_id: str, user_id: str) -> list[dict[str, Any]]:
        return (
            self.client.table("activity_checkins")
            .select("*")
            .eq("activity_id", activity_id)
            .eq("user_id", user_id)
            .order("local_date", desc=True)
            .execute()
            .data
            or []
        )

    def get_activity(self, activity_id: str, user_id: str) -> dict[str, Any] | None:
        result = (
            self.client.table("activities")
            .select("*")
            .eq("id", activity_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return result.data if result and result.data else None

    def update_streak(self, activity_id: str, user_id: str, local_date: str) -> None:
        activity = self.get_activity(activity_id, user_id)
        if not activity:
            return
        checkins = self.get_activity_checkins(activity_id, user_id)
        day = __import__("datetime").date.fromisoformat(local_date)
        current = calculate_streak(checkins, activity, day)
        longest = max(
            int(activity.get("longest_streak") or 0), calculate_longest_streak(checkins, activity)
        )
        self.client.table("activities").update(
            {"current_streak": current, "longest_streak": longest}
        ).eq("id", activity_id).eq("user_id", user_id).execute()
