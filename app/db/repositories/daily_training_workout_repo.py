"""Persistence for one personalized dashboard workout per user and UTC day."""

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class DailyTrainingWorkoutRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: int, workout_date: date) -> dict[str, Any] | None:
        result = await self.db.execute(
            text(
                "SELECT status, title, workout_text, recovery_note, recovery_status, created_at "
                "FROM systemdb.daily_training_workouts "
                "WHERE user_id = :user_id AND workout_date = :workout_date"
            ),
            {"user_id": user_id, "workout_date": workout_date},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def upsert(
        self, user_id: int, workout_date: date, values: dict[str, Any]
    ) -> dict[str, Any]:
        result = await self.db.execute(
            text(
                "INSERT INTO systemdb.daily_training_workouts ("
                "user_id, workout_date, status, title, workout_text, recovery_note, "
                "recovery_status, profile_snapshot) VALUES ("
                ":user_id, :workout_date, :status, :title, :workout_text, :recovery_note, "
                ":recovery_status, CAST(:profile_snapshot AS jsonb)) "
                "ON CONFLICT (user_id, workout_date) DO UPDATE SET "
                "status = EXCLUDED.status, title = EXCLUDED.title, "
                "workout_text = EXCLUDED.workout_text, recovery_note = EXCLUDED.recovery_note, "
                "recovery_status = EXCLUDED.recovery_status, "
                "profile_snapshot = EXCLUDED.profile_snapshot, updated_at = CURRENT_TIMESTAMP "
                "RETURNING status, title, workout_text, recovery_note, recovery_status, created_at"
            ),
            {"user_id": user_id, "workout_date": workout_date, **values},
        )
        return dict(result.mappings().one())
