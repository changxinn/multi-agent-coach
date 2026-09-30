from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.schemas.dashboard import RecoveryDashboardSnapshot
from app.services.daily_training_workout_service import DailyTrainingWorkoutService


def test_generation_prompt_expands_abbreviations_on_first_use(monkeypatch):
    captured_messages = []
    response = Mock(content="Warm-up\nMain work\nCooldown")
    model = Mock()
    model.invoke.side_effect = lambda messages: captured_messages.extend(messages) or response
    from app.services import daily_training_workout_service as module

    monkeypatch.setattr(module, "ChatOpenAI", lambda **_: model)

    DailyTrainingWorkoutService._generate_workout(
        {"fitness_goal": "strength", "fitness_level": "beginner"},
        RecoveryDashboardSnapshot(status="green"),
    )

    system_prompt = captured_messages[0].content
    assert "Rate of Perceived Exertion (RPE)" in system_prompt
    assert "abbreviation may be used alone" in system_prompt


@pytest.mark.asyncio
async def test_daily_training_workout_reuses_existing_recommendation():
    service = DailyTrainingWorkoutService(AsyncMock())
    service.repo.get = AsyncMock(
        return_value={
            "status": "ready",
            "title": "Today’s personalized workout",
            "workout_text": "Warm-up\nMain work\nCooldown",
            "recovery_note": "Recovery looks suitable for the planned effort.",
            "recovery_status": "green",
            "created_at": datetime(2026, 9, 30, tzinfo=UTC),
        }
    )

    result = await service.get(7)

    assert result.reused is True
    assert result.status == "ready"
    assert result.workout_text == "Warm-up\nMain work\nCooldown"
    service.repo.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_red_recovery_returns_deterministic_recovery_workout_without_llm(monkeypatch):
    service = DailyTrainingWorkoutService(AsyncMock())
    service.repo.get = AsyncMock(return_value=None)
    service._recovery_snapshot = AsyncMock(return_value=RecoveryDashboardSnapshot(status="red"))
    service.repo.upsert = AsyncMock(
        return_value={
            "status": "recovery_adjusted",
            "title": "Recovery-focused movement",
            "workout_text": "Choose rest, easy walking, or gentle mobility only.",
            "recovery_note": "Your recovery status is red, so a hard workout is not recommended.",
            "recovery_status": "red",
            "created_at": datetime(2026, 9, 30, tzinfo=UTC),
        }
    )

    async def profile(_, __):
        return {"fitness_goal": "Hyrox", "fitness_level": "beginner"}

    service._generate_workout = lambda *_: pytest.fail("LLM must not run for red recovery")
    from app.services import daily_training_workout_service as module

    monkeypatch.setattr(module.UserProfileService, "get_user_profile", profile)
    result = await service.get(7)

    assert result.status == "recovery_adjusted"
    assert result.recovery_status == "red"
    service.repo.upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_amber_recovery_offloads_generation_and_persists_recommendation(monkeypatch):
    service = DailyTrainingWorkoutService(AsyncMock())
    service.repo.get = AsyncMock(return_value=None)
    service._recovery_snapshot = AsyncMock(return_value=RecoveryDashboardSnapshot(status="amber"))
    service.repo.upsert = AsyncMock(
        return_value={
            "status": "ready",
            "title": "Today’s personalized workout",
            "workout_text": "Warm-up\nMain work\nCooldown",
            "recovery_note": "Recovery is amber today—keep effort controlled and reduce volume if needed.",
            "recovery_status": "amber",
            "created_at": datetime(2026, 9, 30, tzinfo=UTC),
        }
    )
    to_thread = AsyncMock(return_value="Warm-up\nMain work\nCooldown")
    from app.services import daily_training_workout_service as module

    monkeypatch.setattr(
        module.UserProfileService,
        "get_user_profile",
        AsyncMock(return_value={"fitness_goal": "Hyrox", "fitness_level": "beginner"}),
    )
    monkeypatch.setattr(module.asyncio, "to_thread", to_thread)

    result = await service.get(7, refresh=True)

    assert result.reused is False
    assert result.recovery_status == "amber"
    to_thread.assert_awaited_once_with(
        service._generate_workout,
        {"fitness_goal": "Hyrox", "fitness_level": "beginner"},
        RecoveryDashboardSnapshot(status="amber"),
    )
    service.repo.upsert.assert_awaited_once()