from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def calculate_streak(
    checkins: list[dict[str, Any]],
    activity: dict[str, Any],
    today: date,
) -> int:
    """Calculate current streak for an activity based on DATA_MODEL.md rules.

    A period is a local calendar day for daily/weekdays, or a local ISO week
    for weekly/custom. A period is satisfied when it contains the required
    number of approved check-ins. The current streak is the number of
    consecutive satisfied periods ending with the most recently completed
    eligible period.
    """
    cadence = activity.get("cadence_type", "daily")
    if activity.get("status") in {"paused", "completed", "archived"}:
        return 0
    start_date_str = activity.get("start_date")
    if not start_date_str:
        return 0

    start_date = (
        date.fromisoformat(start_date_str) if isinstance(start_date_str, str) else start_date_str
    )
    if today < start_date:
        return 0

    approved_dates: set[date] = set()
    for c in checkins:
        if c.get("status") != "approved":
            continue
        d = c.get("local_date")
        if isinstance(d, str):
            d = date.fromisoformat(d)
        if d and d >= start_date:
            approved_dates.add(d)

    if not approved_dates:
        return 0

    if cadence == "daily":
        return _current_daily(approved_dates, start_date, today)
    elif cadence == "weekdays":
        return _current_weekdays(approved_dates, start_date, today)
    elif cadence == "weekly":
        return _streak_weekly(approved_dates, start_date, today)
    elif cadence == "custom":
        target = activity.get("cadence_config", {}).get("target_per_period", 1)
        return _streak_custom(approved_dates, start_date, today, target)
    return 0


def _is_eligible_weekday(d: date) -> bool:
    return d.weekday() < 5


def _most_recent_checkin(approved: set[date], max_date: date) -> date | None:
    candidates = {d for d in approved if d <= max_date}
    return max(candidates) if candidates else None


def _streak_daily(approved: set[date], start: date, today: date) -> int:
    last = _most_recent_checkin(approved, today)
    if last is None:
        return 0
    streak = 0
    current = last
    while current >= start:
        if current in approved:
            streak += 1
            current -= timedelta(days=1)
        else:
            break
    return streak


def _current_daily(approved: set[date], start: date, today: date) -> int:
    anchor = today if today in approved else today - timedelta(days=1)
    if anchor < start or anchor not in approved:
        return 0
    return _streak_daily(approved, start, anchor)


def _streak_weekdays(approved: set[date], start: date, today: date) -> int:
    last = _most_recent_checkin(approved, today)
    if last is None:
        return 0
    streak = 0
    current = last
    while current >= start:
        if _is_eligible_weekday(current):
            if current in approved:
                streak += 1
            else:
                break
        current -= timedelta(days=1)
    return streak


def _current_weekdays(approved: set[date], start: date, today: date) -> int:
    anchor = today
    while anchor >= start and not _is_eligible_weekday(anchor):
        anchor -= timedelta(days=1)
    if anchor not in approved:
        anchor -= timedelta(days=1)
        while anchor >= start and not _is_eligible_weekday(anchor):
            anchor -= timedelta(days=1)
    if anchor < start or anchor not in approved:
        return 0
    return _streak_weekdays(approved, start, anchor)


def calculate_longest_streak(checkins: list[dict[str, Any]], activity: dict[str, Any]) -> int:
    """Return the longest completed Daily/Weekdays run without treating misses as failure UI."""
    start_value = activity.get("start_date")
    if not start_value:
        return 0
    start = date.fromisoformat(start_value) if isinstance(start_value, str) else start_value
    approved = {
        date.fromisoformat(item["local_date"])
        if isinstance(item.get("local_date"), str)
        else item.get("local_date")
        for item in checkins
        if item.get("status") == "approved" and item.get("local_date")
    }
    approved = {item for item in approved if item and item >= start}
    if not approved:
        return 0
    cadence = activity.get("cadence_type")
    if cadence not in {"daily", "weekdays"}:
        return max((calculate_streak(checkins, activity, item) for item in approved), default=0)
    longest = 0
    run = 0
    cursor = start
    last = max(approved)
    while cursor <= last:
        eligible = cadence == "daily" or _is_eligible_weekday(cursor)
        if eligible:
            if cursor in approved:
                run += 1
                longest = max(longest, run)
            else:
                run = 0
        cursor += timedelta(days=1)
    return longest


def _streak_weekly(approved: set[date], start: date, today: date) -> int:
    streak = 0
    current_week_start = today - timedelta(days=today.weekday())
    while current_week_start >= start:
        week_has_checkin = any(
            current_week_start <= d <= current_week_start + timedelta(days=6) for d in approved
        )
        if week_has_checkin:
            streak += 1
            current_week_start -= timedelta(weeks=1)
        else:
            break
    return streak


def _streak_custom(approved: set[date], start: date, today: date, target: int) -> int:
    streak = 0
    current_week_start = today - timedelta(days=today.weekday())
    while current_week_start >= start:
        count = sum(
            1 for d in approved if current_week_start <= d <= current_week_start + timedelta(days=6)
        )
        if count >= target:
            streak += 1
            current_week_start -= timedelta(weeks=1)
        else:
            break
    return streak
