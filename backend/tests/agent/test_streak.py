from datetime import date

from app.agent.streak import calculate_longest_streak, calculate_streak


def _activity(cadence_type: str = "daily", start_date: str = "2026-07-01") -> dict:
    return {"cadence_type": cadence_type, "start_date": start_date}


def _checkin(local_date: str, status: str = "approved") -> dict:
    return {"local_date": local_date, "status": status}


class TestStreakDaily:
    def test_no_checkins_returns_zero(self) -> None:
        assert calculate_streak([], _activity(), date(2026, 7, 18)) == 0

    def test_single_checkin_today_returns_one(self) -> None:
        checkins = [_checkin("2026-07-18")]
        assert calculate_streak(checkins, _activity(), date(2026, 7, 18)) == 1

    def test_consecutive_days(self) -> None:
        checkins = [_checkin("2026-07-16"), _checkin("2026-07-17"), _checkin("2026-07-18")]
        assert calculate_streak(checkins, _activity(cadence_type="daily"), date(2026, 7, 18)) == 3

    def test_broken_streak(self) -> None:
        checkins = [_checkin("2026-07-16"), _checkin("2026-07-18")]
        assert calculate_streak(checkins, _activity(cadence_type="daily"), date(2026, 7, 18)) == 1

    def test_only_discarded_checkins(self) -> None:
        checkins = [_checkin("2026-07-18", status="discarded")]
        assert calculate_streak(checkins, _activity(), date(2026, 7, 18)) == 0

    def test_before_start_date(self) -> None:
        checkins = [_checkin("2026-06-30")]
        assert (
            calculate_streak(checkins, _activity(start_date="2026-07-01"), date(2026, 7, 18)) == 0
        )

    def test_non_consecutive_returns_one(self) -> None:
        checkins = [_checkin("2026-07-17"), _checkin("2026-07-15")]
        assert calculate_streak(checkins, _activity(), date(2026, 7, 18)) == 1

    def test_yesterdays_miss_resets_the_current_rhythm(self) -> None:
        checkins = [_checkin("2026-07-16"), _checkin("2026-07-17")]
        assert calculate_streak(checkins, _activity(), date(2026, 7, 19)) == 0

    def test_longest_rhythm_survives_a_later_miss(self) -> None:
        checkins = [_checkin("2026-07-14"), _checkin("2026-07-15"), _checkin("2026-07-16")]
        assert calculate_longest_streak(checkins, _activity()) == 3


class TestStreakWeekdays:
    def test_skips_weekends(self) -> None:
        # 2026-07-18 is Saturday — no check-in needed
        checkins = [_checkin("2026-07-17")]  # Friday
        assert (
            calculate_streak(checkins, _activity(cadence_type="weekdays"), date(2026, 7, 18)) == 1
        )

    def test_breaks_on_missed_weekday(self) -> None:
        # Wednesday (07-15) and Friday (07-17) but missed Thursday (07-16)
        checkins = [_checkin("2026-07-15"), _checkin("2026-07-17")]
        assert (
            calculate_streak(checkins, _activity(cadence_type="weekdays"), date(2026, 7, 18)) == 1
        )


class TestStreakWeekly:
    def test_one_checkin_in_week(self) -> None:
        checkins = [_checkin("2026-07-14")]  # Tuesday of week starting 07-13
        assert calculate_streak(checkins, _activity(cadence_type="weekly"), date(2026, 7, 18)) == 1

    def test_consecutive_weeks(self) -> None:
        checkins = [_checkin("2026-07-07"), _checkin("2026-07-14")]
        assert calculate_streak(checkins, _activity(cadence_type="weekly"), date(2026, 7, 18)) == 2

    def test_missed_week_breaks(self) -> None:
        checkins = [_checkin("2026-06-29"), _checkin("2026-07-14")]
        assert calculate_streak(checkins, _activity(cadence_type="weekly"), date(2026, 7, 18)) == 1
