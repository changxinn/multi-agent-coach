import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TrainingProgressRepository:
    """SQL boundary for Main API-owned training preferences and workout history."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_preferences(self, user_id: int) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("SELECT equipment, training_days_per_week, session_duration_minutes, preferences, updated_at FROM systemdb.training_preferences WHERE user_id=:user_id"),
            {"user_id": user_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def save_preferences(self, user_id: int, values: dict[str, Any]) -> dict[str, Any]:
        result = await self.db.execute(
            text("INSERT INTO systemdb.training_preferences (user_id,equipment,training_days_per_week,session_duration_minutes,preferences) VALUES (:user_id,CAST(:equipment AS jsonb),:days,:duration,CAST(:preferences AS jsonb)) ON CONFLICT (user_id) DO UPDATE SET equipment=EXCLUDED.equipment,training_days_per_week=EXCLUDED.training_days_per_week,session_duration_minutes=EXCLUDED.session_duration_minutes,preferences=EXCLUDED.preferences,updated_at=CURRENT_TIMESTAMP RETURNING equipment,training_days_per_week,session_duration_minutes,preferences,updated_at"),
            {"user_id": user_id, "equipment": json.dumps(values["equipment"]), "days": values["training_days_per_week"], "duration": values["session_duration_minutes"], "preferences": json.dumps(values["preferences"])},
        )
        return dict(result.mappings().one())

    async def log_workout(self, user_id: int, values: dict[str, Any], idempotency_key: str | None) -> dict[str, Any]:
        if idempotency_key:
            existing = await self.db.execute(text("SELECT id,occurred_at,description,duration_minutes,session_rpe,notes,exercise_performance,metadata,created_at FROM systemdb.workout_progress WHERE user_id=:user_id AND idempotency_key=:key"), {"user_id": user_id, "key": idempotency_key})
            row = existing.mappings().first()
            if row:
                return {**dict(row), "reused": True}
        result = await self.db.execute(
            text("INSERT INTO systemdb.workout_progress (user_id,occurred_at,description,duration_minutes,session_rpe,notes,exercise_performance,metadata,idempotency_key) VALUES (:user_id,:occurred_at,:description,:duration,:rpe,:notes,CAST(:performance AS jsonb),'{}'::jsonb,:key) RETURNING id,occurred_at,description,duration_minutes,session_rpe,notes,exercise_performance,metadata,created_at"),
            {"user_id": user_id, "occurred_at": values["occurred_at"], "description": values["description"], "duration": values["duration_minutes"], "rpe": values["session_rpe"], "notes": values["notes"], "performance": json.dumps(values["exercise_performance"]), "key": idempotency_key},
        )
        return {**dict(result.mappings().one()), "reused": False}

    async def list_workouts(self, user_id: int, days: int, limit: int) -> list[dict[str, Any]]:
        since = datetime.now(UTC) - timedelta(days=days)
        result = await self.db.execute(text("SELECT id,occurred_at,description,duration_minutes,session_rpe,notes,exercise_performance,metadata,created_at FROM systemdb.workout_progress WHERE user_id=:user_id AND occurred_at>=:since ORDER BY occurred_at DESC,id DESC LIMIT :limit"), {"user_id": user_id, "since": since, "limit": limit})
        return [dict(row) for row in result.mappings()]

    async def progress(self, user_id: int, days: int) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=days)
        result = await self.db.execute(text("SELECT COUNT(*) AS workout_count, AVG(session_rpe) AS average_rpe, SUM(duration_minutes) AS total_duration_minutes, MAX(occurred_at) AS last_workout_at FROM systemdb.workout_progress WHERE user_id=:user_id AND occurred_at>=:since"), {"user_id": user_id, "since": since})
        return dict(result.mappings().one())