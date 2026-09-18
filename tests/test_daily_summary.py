from datetime import UTC, datetime

from agents.summarizer import build_daily_summary, strip_daily_summary_heading
from app.db.repositories.coach_events_repo import utc_day_bounds


def test_daily_summary_covers_training_recovery_and_nutrition():
    text = build_daily_summary(
        {
            "user_profile": {"goal": "Hyrox", "fitness_level": "beginner"},
            "messages": [],
        },
        progress="Workouts logged: 0",
    )
    assert "Your day at a glance" not in text
    assert "Recovery emphasis" in text
    assert "Fuel:" in text
    assert "bestie" in text.lower()
    assert "Progress Summary" not in text
    assert "Workouts logged" not in text


def test_utc_day_bounds_are_timezone_aware():
    start, end = utc_day_bounds(datetime(2026, 9, 18, 15, 30, tzinfo=UTC))
    assert start.tzinfo is not None
    assert end.tzinfo is not None
    assert start.isoformat().startswith("2026-09-18T00:00:00")
    assert end.isoformat().startswith("2026-09-19T00:00:00")


def test_strip_daily_summary_heading_drops_card_title():
    text = strip_daily_summary_heading(
        "Your day at a glance:\nEasy session today. You got this bestie!"
    )
    assert not text.lower().startswith("your day at a glance")
    assert "Easy session today" in text
