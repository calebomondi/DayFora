from __future__ import annotations

import json
from datetime import date, datetime
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from supabase import Client


def _activity_due(activity: dict, local_date: date) -> bool:
    if activity.get("status") != "active":
        return False
    start = date.fromisoformat(str(activity["start_date"]))
    end = date.fromisoformat(str(activity["end_date"])) if activity.get("end_date") else None
    if local_date < start or (end and local_date > end):
        return False
    return activity.get("cadence_type") == "daily" or (
        activity.get("cadence_type") == "weekdays" and local_date.weekday() < 5
    )


def dispatch_due_reminders(client: Client, now: datetime | None = None) -> int:
    now = now or datetime.now(tz=ZoneInfo("UTC"))
    sent = 0
    for preference in client.table("notification_preferences").select("*").execute().data or []:
        local_now = now.astimezone(ZoneInfo(preference.get("timezone") or "UTC"))
        kinds = []
        if preference.get("diary_enabled") and preference.get("diary_reminder_time", "")[
            :5
        ] == local_now.strftime("%H:%M"):
            kinds.append(("diary", "A small reflection is enough to begin."))
        if preference.get("activity_enabled") and preference.get("activity_reminder_time", "")[
            :5
        ] == local_now.strftime("%H:%M"):
            local_date = local_now.date()
            activities = (
                client.table("activities")
                .select("*")
                .eq("user_id", preference["user_id"])
                .eq("status", "active")
                .execute()
                .data
                or []
            )
            checkins = (
                client.table("activity_checkins")
                .select("activity_id")
                .eq("user_id", preference["user_id"])
                .eq("status", "approved")
                .eq("local_date", local_date.isoformat())
                .execute()
                .data
                or []
            )
            completed = {str(checkin["activity_id"]) for checkin in checkins}
            due = [
                activity
                for activity in activities
                if _activity_due(activity, local_date) and str(activity["id"]) not in completed
            ]
            if due:
                next_step = (
                    client.table("activity_checkins")
                    .select("next_small_step")
                    .eq("activity_id", due[0]["id"])
                    .eq("status", "approved")
                    .order("local_date", desc=True)
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
                step = next_step[0].get("next_small_step") if next_step else None
                names = ", ".join(activity["title"] for activity in due[:2])
                body = f"A moment for your commitments: {names}."
                if step:
                    body = f"{body} Smallest next step: {step}"
                kinds.append(("activity", body))
        for kind, body in kinds:
            try:
                client.table("notification_deliveries").insert(
                    {
                        "user_id": preference["user_id"],
                        "kind": kind,
                        "local_date": local_now.date().isoformat(),
                    }
                ).execute()
            except Exception:
                continue
            rows = (
                client.table("device_tokens")
                .select("expo_push_token")
                .eq("user_id", preference["user_id"])
                .is_("revoked_at", "null")
                .execute()
                .data
                or []
            )
            if rows:
                request = Request(
                    "https://exp.host/--/api/v2/push/send",
                    data=json.dumps(
                        [
                            {
                                "to": row["expo_push_token"],
                                "title": "DayFora",
                                "body": body,
                                "sound": "default",
                            }
                            for row in rows
                        ]
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=10):
                    pass
            sent += 1
    return sent
