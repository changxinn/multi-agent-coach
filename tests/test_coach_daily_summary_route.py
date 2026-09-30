from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.routes import coach


@pytest.mark.asyncio
async def test_daily_summary_offloads_synchronous_summarizer(monkeypatch):
    repo = Mock()
    repo.get_today_daily_summary = AsyncMock(return_value=None)
    repo.add_summary = AsyncMock(
        return_value=SimpleNamespace(
            summary_text="Easy session today. You got this bestie!",
            created_at=datetime(2026, 9, 30, tzinfo=UTC),
        )
    )
    profile_service = Mock()
    profile_service.get_user_profile = AsyncMock(
        return_value={"fitness_goal": "Hyrox", "fitness_level": "beginner"}
    )
    session_manager = Mock()
    session_manager.list_user_messages = AsyncMock(return_value=[])
    to_thread = AsyncMock(return_value="Easy session today. You got this bestie!")

    monkeypatch.setattr(coach, "CoachEventsRepository", lambda _: repo)
    monkeypatch.setattr(coach, "UserProfileService", lambda _: profile_service)
    monkeypatch.setattr(coach, "get_session_manager", lambda: session_manager)
    monkeypatch.setattr(coach.asyncio, "to_thread", to_thread)

    response = await coach.generate_daily_summary(
        refresh=True,
        current_user={"id": 7, "name": "Alex"},
        db=Mock(),
    )

    assert response.summary == "Easy session today. You got this bestie!"
    assert response.reused is False
    to_thread.assert_awaited_once()
    assert to_thread.await_args.args[0].__name__ == "summarizer"
    assert to_thread.await_args.args[1] == {
        "summary_kind": "daily",
        "messages": [],
        "user_profile": {
            "name": "Alex",
            "goal": "Hyrox",
            "fitness_level": "beginner",
            "user_id": 7,
        },
    }
    repo.add_summary.assert_awaited_once_with(
        user_id=7,
        session_id=None,
        summary_type="daily",
        summary_text="Easy session today. You got this bestie!",
    )