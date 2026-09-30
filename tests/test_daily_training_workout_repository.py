from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.db.repositories.daily_training_workout_repo import (
    DailyTrainingWorkoutRepository,
)


@pytest.mark.asyncio
async def test_get_returns_mapped_workout_and_binds_user_and_date():
    row = {"status": "ready", "title": "Workout"}
    result = Mock()
    result.mappings.return_value.first.return_value = row
    db = AsyncMock()
    db.execute.return_value = result

    workout = await DailyTrainingWorkoutRepository(db).get(7, date(2026, 9, 30))

    assert workout == row
    _, parameters = db.execute.await_args.args
    assert parameters == {"user_id": 7, "workout_date": date(2026, 9, 30)}


@pytest.mark.asyncio
async def test_get_returns_none_when_no_workout_exists():
    result = Mock()
    result.mappings.return_value.first.return_value = None
    db = AsyncMock()
    db.execute.return_value = result

    assert await DailyTrainingWorkoutRepository(db).get(7, date(2026, 9, 30)) is None


@pytest.mark.asyncio
async def test_upsert_returns_database_row_and_includes_profile_snapshot():
    row = {
        "status": "ready",
        "title": "Workout",
        "workout_text": "Warm-up",
        "recovery_note": None,
        "recovery_status": "green",
        "created_at": datetime(2026, 9, 30, tzinfo=UTC),
    }
    result = Mock()
    result.mappings.return_value.one.return_value = row
    db = AsyncMock()
    db.execute.return_value = result
    values = {**row, "profile_snapshot": '{"fitness_goal": "strength"}'}

    saved = await DailyTrainingWorkoutRepository(db).upsert(7, date(2026, 9, 30), values)

    assert saved == row
    statement, parameters = db.execute.await_args.args
    assert "ON CONFLICT (user_id, workout_date) DO UPDATE" in str(statement)
    assert parameters["user_id"] == 7
    assert parameters["profile_snapshot"] == values["profile_snapshot"]