from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from supabase import Client

from app.agent.streak import calculate_longest_streak, calculate_streak


def is_eligible_day(activity: dict[str, Any], local_date: date) -> bool:
    """Return whether a supported MVP activity expects a check-in on this date."""
    if activity.get("status") != "active":
        return False
    start = activity.get("start_date")
    end = activity.get("end_date")
    start_date = date.fromisoformat(start) if isinstance(start, str) else start
    end_date = date.fromisoformat(end) if isinstance(end, str) else end
    if not start_date or local_date < start_date or (end_date and local_date > end_date):
        return False
    return activity.get("cadence_type") == "daily" or (
        activity.get("cadence_type") == "weekdays" and local_date.weekday() < 5
    )


def refresh_activity_consistency(
    client: Client, activity: dict[str, Any], user_id: str, today: date
) -> dict[str, int]:
    """Persist current/longest streaks and one idempotent neutral reset per missed day.

    Today's open check-in is never treated as a miss. Paused and completed activity
    history is deliberately left untouched.
    """
    if activity.get("status") != "active":
        return {
            "current_streak": int(activity.get("current_streak") or 0),
            "longest_streak": int(activity.get("longest_streak") or 0),
        }

    checkins = (
        client.table("activity_checkins")
        .select("local_date, status")
        .eq("activity_id", activity["id"])
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    reset_events = (
        client.table("activity_events")
        .select("local_date")
        .eq("activity_id", activity["id"])
        .eq("event_type", "streak_reset")
        .execute()
        .data
        or []
    )
    reset_dates = {str(event["local_date"]) for event in reset_events}
    approved_dates = {
        str(checkin["local_date"])
        for checkin in checkins
        if checkin.get("status") == "approved" and checkin.get("local_date")
    }
    start = activity.get("start_date")
    start_date = date.fromisoformat(start) if isinstance(start, str) else start
    if start_date:
        cursor = start_date
        while cursor < today:
            if is_eligible_day(activity, cursor) and cursor.isoformat() not in approved_dates:
                if cursor.isoformat() not in reset_dates:
                    previous = calculate_streak(checkins, activity, cursor - timedelta(days=1))
                    client.table("activity_events").upsert(
                        {
                            "activity_id": activity["id"],
                            "user_id": user_id,
                            "local_date": cursor.isoformat(),
                            "event_type": "streak_reset",
                            "metadata": {"previous_streak": previous},
                        },
                        on_conflict="activity_id,local_date,event_type",
                    ).execute()
            cursor += timedelta(days=1)

    current = calculate_streak(checkins, activity, today)
    longest = max(
        int(activity.get("longest_streak") or 0), calculate_longest_streak(checkins, activity)
    )
    client.table("activities").update({"current_streak": current, "longest_streak": longest}).eq(
        "id", activity["id"]
    ).eq("user_id", user_id).execute()
    return {"current_streak": current, "longest_streak": longest}
