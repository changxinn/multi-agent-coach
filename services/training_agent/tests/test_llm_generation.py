from datetime import date
from unittest.mock import AsyncMock, Mock

import pytest

from services.training_agent.app import service as module
from services.training_agent.app.schemas import DailyWorkoutRequest
from services.training_agent.app.service import TrainingService


@pytest.mark.asyncio
async def test_daily_workout_uses_llm_when_recovery_permits(monkeypatch):
    db = Mock()
    existing = Mock()
    existing.mappings.return_value.first.return_value = None
    saved = Mock()
    saved.mappings.return_value.one.return_value = {
        "status": "ready",
        "title": "LLM workout",
        "workout_text": "Warm-up\nMain work\nCooldown",
        "recovery_note": None,
        "recovery_status": "green",
        "created_at": "2026-10-08T00:00:00Z",
    }
    db.execute = AsyncMock(side_effect=[existing, saved])
    service = TrainingService(db)
    monkeypatch.setattr(
        service,
        "context",
        AsyncMock(return_value={"profile": {"fitness_goal": "strength"}}),
    )
    monkeypatch.setattr(
        service, "profile", AsyncMock(return_value={"fitness_goal": "strength"})
    )
    monkeypatch.setattr(module.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        service,
        "_llm_json",
        lambda *_: {
            "title": "LLM workout",
            "workout_text": "Warm-up\nMain work\nCooldown",
        },
    )

    result = await service.daily_workout(
        DailyWorkoutRequest(user_id=7, date=date(2026, 10, 8), recovery_status="green")
    )

    assert result["generation_source"] == "llm"


@pytest.mark.asyncio
async def test_red_recovery_bypasses_llm(monkeypatch):
    db = Mock()
    existing = Mock()
    existing.mappings.return_value.first.return_value = None
    saved = Mock()
    saved.mappings.return_value.one.return_value = {
        "status": "recovery_adjusted",
        "title": "Recovery-focused movement",
        "workout_text": "Skip structured training today.",
        "recovery_note": None,
        "recovery_status": "red",
        "created_at": "2026-10-08T00:00:00Z",
    }
    db.execute = AsyncMock(side_effect=[existing, saved])
    service = TrainingService(db)
    monkeypatch.setattr(
        service, "_llm_json", Mock(side_effect=AssertionError("LLM must not run"))
    )
    monkeypatch.setattr(
        service, "profile", AsyncMock(return_value={"fitness_goal": "strength"})
    )

    result = await service.daily_workout(
        DailyWorkoutRequest(user_id=7, date=date(2026, 10, 8), recovery_status="red")
    )

    assert result["generation_source"] == "recovery_safety_gate"
