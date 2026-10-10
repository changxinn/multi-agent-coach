from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from services.training_agent.app import service as module
from services.training_agent.app.schemas import DailyWorkoutRequest
from services.training_agent.app.service import TrainingService


def result(*, first=None, one=None, rows=None, scalar=None):
    mappings = Mock()
    mappings.first.return_value = first
    mappings.one.return_value = one
    value = Mock()
    value.mappings.return_value = rows if rows is not None else mappings
    value.scalar_one.return_value = scalar
    return value


@pytest.mark.asyncio
async def test_profile_preferences_and_persistence_methods():
    db = Mock()
    db.execute = AsyncMock(
        side_effect=[
            result(first=None),
            result(one={"fitness_goal": "strength"}),
            result(first=None),
            result(one={"equipment": ["barbell"]}),
        ]
    )
    service = TrainingService(db)
    assert (await service.profile(1))["fitness_goal"] == "general fitness"
    assert await service.save_profile(
        SimpleNamespace(user_id=1, fitness_goal="strength", fitness_level="advanced")
    ) == {"fitness_goal": "strength"}
    assert (await service.preferences(1))["equipment"] == []
    assert await service.save_preferences(
        SimpleNamespace(
            user_id=1,
            equipment=["barbell"],
            training_days_per_week=3,
            session_duration_minutes=45,
            preferences={},
        )
    ) == {"equipment": ["barbell"]}


@pytest.mark.asyncio
async def test_workout_progress_context_and_lists():
    db = Mock()
    db.execute = AsyncMock(
        side_effect=[
            result(one={"id": 1}),
            result(rows=[{"id": 2}]),
            result(
                one={
                    "workout_count": 6,
                    "average_rpe": 9,
                    "total_duration_minutes": 100,
                    "last_workout_at": None,
                }
            ),
        ]
    )
    service = TrainingService(db)
    payload = SimpleNamespace(
        user_id=1,
        occurred_at="now",
        description="lift",
        duration_minutes=30,
        session_rpe=8,
        notes=None,
        exercise_performance=[],
    )
    with pytest.raises(ValueError, match="Idempotency-Key"):
        await service.log_workout(payload, None)
    assert await service.log_workout(payload, "key") == {"id": 1}
    assert await service.list_workouts(1, 7, 5) == [{"id": 2}]
    assert (await service.progress(1, 7))["plateau_detected"] is True

    service.profile = AsyncMock(return_value={"fitness_goal": "strength"})
    service.preferences = AsyncMock(return_value={"equipment": []})
    service.progress = AsyncMock(return_value={})
    service.list_workouts = AsyncMock(return_value=[])
    assert (await service.context(1))["profile"]["fitness_goal"] == "strength"


@pytest.mark.asyncio
async def test_daily_workout_and_program_fallbacks_persist(monkeypatch):
    db = Mock()
    db.execute = AsyncMock(
        side_effect=[
            result(first=None),
            result(
                one={
                    "status": "ready",
                    "title": "Fallback",
                    "workout_text": "Warm-up",
                    "recovery_note": None,
                    "recovery_status": "amber",
                    "created_at": "now",
                }
            ),
            result(scalar=2),
            result(one={"id": 9, "version": 3, "created_at": "now"}),
            result(),
        ]
    )
    service = TrainingService(db)
    service.context = AsyncMock(return_value={"profile": {"fitness_goal": "strength"}})
    service.profile = AsyncMock(return_value={"fitness_goal": "strength"})
    monkeypatch.setattr(
        module.asyncio,
        "to_thread",
        AsyncMock(side_effect=[RuntimeError("down"), RuntimeError("down")]),
    )

    daily = await service.daily_workout(
        DailyWorkoutRequest(user_id=1, date=date(2026, 1, 1), recovery_status="amber")
    )
    assert daily["generation_source"] == "deterministic_fallback"
    program = await service.generate_program(1, "amber", "fatigue")
    assert program["generation_source"] == "deterministic_fallback"
    assert program["program"]["target_rpe"] == "6-7"
    with pytest.raises(ValueError, match="does not permit"):
        await service.generate_program(1, "red")


@pytest.mark.asyncio
async def test_exercise_guidance_llm_success_and_safe_failure(monkeypatch):
    monkeypatch.setattr(module.settings, "OPENAI_API_KEY", "key")
    model = Mock()
    model.invoke.return_value = Mock(content="Keep your ribs down.")
    monkeypatch.setattr(module, "ChatOpenAI", lambda **_: model)
    assert (
        await TrainingService._generate_exercise_guidance("squat")
        == "Keep your ribs down."
    )
    model.invoke.return_value = Mock(content="system prompt")
    assert (
        await TrainingService._generate_exercise_guidance("squat")
        == module.SAFE_GUIDANCE_FALLBACK
    )


@pytest.mark.asyncio
async def test_daily_recommendation_reuse_llm_json_and_program_list(monkeypatch):
    existing = {
        "status": "ready",
        "title": "Saved",
        "workout_text": "Warm-up",
        "recovery_note": None,
        "recovery_status": "green",
        "created_at": "now",
    }
    db = Mock()
    db.execute = AsyncMock(
        side_effect=[result(first=existing), result(rows=[{"id": 3}])]
    )
    service = TrainingService(db)
    reused = await service.daily_workout(
        DailyWorkoutRequest(user_id=1, date=date(2026, 1, 1), recovery_status="green")
    )
    assert reused["reused"] is True
    assert await service.list_programs(1) == [{"id": 3}]

    monkeypatch.setattr(module.settings, "OPENAI_API_KEY", "key")
    model = Mock()
    model.invoke.return_value = Mock(content='{"days": [], "target_rpe": "7"}')
    monkeypatch.setattr(module, "ChatOpenAI", lambda **_: model)
    assert TrainingService._llm_json("prompt", {}, "green")["target_rpe"] == "7"
