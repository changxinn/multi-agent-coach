from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.training_progress_repo import TrainingProgressRepository


class TrainingProgressService:
    def __init__(self, db: AsyncSession):
        self.repo = TrainingProgressRepository(db)

    async def preferences(self, user_id: int) -> dict[str, Any]:
        return await self.repo.get_preferences(user_id) or {"equipment": [], "training_days_per_week": None, "session_duration_minutes": None, "preferences": {}}

    async def save_preferences(self, user_id: int, values: dict[str, Any]) -> dict[str, Any]:
        return await self.repo.save_preferences(user_id, values)

    async def log_workout(self, user_id: int, values: dict[str, Any], idempotency_key: str | None) -> dict[str, Any]:
        return await self.repo.log_workout(user_id, values, idempotency_key)

    async def list_workouts(self, user_id: int, days: int, limit: int) -> list[dict[str, Any]]:
        return await self.repo.list_workouts(user_id, days, limit)

    async def progress(self, user_id: int, days: int) -> dict[str, Any]:
        summary = await self.repo.progress(user_id, days)
        summary["plateau_detected"] = bool(summary["workout_count"] >= 6 and summary["average_rpe"] and float(summary["average_rpe"]) >= 8.5)
        return summary