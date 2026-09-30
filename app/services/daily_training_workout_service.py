"""Recovery-aware, persisted Training Planner recommendations for the dashboard."""

import asyncio
import json
import logging
from datetime import UTC, date, datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.dashboard import RecoveryDashboardSnapshot, TrainingWorkoutResponse
from app.db.repositories.daily_training_workout_repo import (
    DailyTrainingWorkoutRepository,
)
from app.services.daily_command_center_service import DailyCommandCenterService
from app.services.nutrition_service import NutritionService
from app.services.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)


class DailyTrainingWorkoutService:
    """Creates at most one usable Training Planner recommendation per user/day."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DailyTrainingWorkoutRepository(db)

    async def get(
        self, user_id: int, *, refresh: bool = False
    ) -> TrainingWorkoutResponse:
        workout_date = datetime.now(UTC).date()
        if not refresh:
            existing = await self.repo.get(user_id, workout_date)
            if existing:
                return self._response(existing, reused=True)

        profile = await UserProfileService(self.db).get_user_profile(user_id)
        recovery = await self._recovery_snapshot(user_id, workout_date)
        values = await self._recommendation(profile, recovery)
        if values["status"] == "unavailable":
            return TrainingWorkoutResponse(
                **values, generated_at=datetime.now(UTC), reused=False
            )

        saved = await self.repo.upsert(
            user_id,
            workout_date,
            {
                **values,
                "profile_snapshot": json.dumps(
                    {
                        "fitness_goal": profile["fitness_goal"],
                        "fitness_level": profile["fitness_level"],
                    }
                ),
            },
        )
        return self._response(saved, reused=False)

    async def _recovery_snapshot(
        self, user_id: int, workout_date: date
    ) -> RecoveryDashboardSnapshot:
        command_center = DailyCommandCenterService(self.db, NutritionService(self.db))
        return await command_center._recovery_snapshot(
            user_id, workout_date, workout_date, []
        )

    async def _recommendation(
        self, profile: dict[str, Any], recovery: RecoveryDashboardSnapshot
    ) -> dict[str, Any]:
        if recovery.status == "escalate":
            return {
                "status": "recovery_adjusted",
                "title": "Recovery takes priority today",
                "workout_text": (
                    "Do not start a training session from the dashboard today. Follow your "
                    "recovery guidance and seek appropriate professional care when advised."
                ),
                "recovery_note": "Your latest recovery assessment requires extra caution.",
                "recovery_status": recovery.status,
            }
        if recovery.status == "red":
            return {
                "status": "recovery_adjusted",
                "title": "Recovery-focused movement",
                "workout_text": (
                    "Choose rest, easy walking, or gentle mobility only. Avoid hard intervals, "
                    "heavy lifting, and training through worsening symptoms."
                ),
                "recovery_note": "Your recovery status is red, so a hard workout is not recommended.",
                "recovery_status": recovery.status,
            }

        try:
            workout_text = await asyncio.to_thread(
                self._generate_workout, profile, recovery
            )
        except Exception:
            logger.exception("Training Planner dashboard workout generation failed")
            return {
                "status": "unavailable",
                "title": "Today’s workout is unavailable",
                "workout_text": "Try again shortly to generate your personalized session.",
                "recovery_note": None,
                "recovery_status": recovery.status,
            }
        return {
            "status": "ready",
            "title": "Today’s personalized workout",
            "workout_text": workout_text,
            "recovery_note": self._recovery_note(recovery),
            "recovery_status": recovery.status,
        }

    @staticmethod
    def _generate_workout(
        profile: dict[str, Any], recovery: RecoveryDashboardSnapshot
    ) -> str:
        intensity = (
            "RPE 6–7 with reduced volume" if recovery.status == "amber" else "RPE 7"
        )
        system_prompt = (
            "You are Alex, a strength and conditioning coach. Create one safe, personalized "
            "workout for today. Return plain text only with labeled sections: Warm-up, Main work, "
            "and Cooldown. Include sets, reps or time, a total duration of 30–45 minutes, and a "
            "target RPE. Use broadly accessible bodyweight, dumbbell, or gym alternatives; do not "
            "use an abbreviation without first spelling out its full term followed by the abbreviation "
            "in parentheses (for example, Rate of Perceived Exertion (RPE)); after that first use, "
            "the abbreviation may be used alone. Do not assume injuries, equipment, a schedule, or "
            "previous workouts. Do not log anything, "
            "request a tool, write Action:, claim medical expertise, or give medical advice. Keep "
            "the workout under 220 words."
        )
        user_prompt = (
            f"Athlete goal: {profile['fitness_goal']}\n"
            f"Fitness level: {profile['fitness_level']}\n"
            f"Recovery status: {recovery.status}\n"
            "Recovery signals: "
            f"sleep={recovery.sleep_duration_minutes or 'not logged'} minutes, "
            f"energy={recovery.energy or 'not logged'}, "
            f"soreness={recovery.soreness or 'not logged'}, "
            f"stress={recovery.stress or 'not logged'}.\n"
            f"Intensity constraint: {intensity}.\n\nGenerate today’s workout now."
        )
        response = ChatOpenAI(model="gpt-5-nano", temperature=0.3, timeout=45).invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        workout_text = str(response.content).strip()
        if not workout_text:
            raise ValueError("Training Planner returned an empty dashboard workout")
        return workout_text[:4000]

    @staticmethod
    def _recovery_note(recovery: RecoveryDashboardSnapshot) -> str:
        if recovery.status == "amber":
            return "Recovery is amber today—keep effort controlled and reduce volume if needed."
        if recovery.status == "no_assessment":
            return "No recovery assessment is available, so this is a conservative session."
        if recovery.status == "unavailable":
            return "Recovery data is temporarily unavailable, so this is a conservative session."
        return "Recovery looks suitable for the planned effort."

    @staticmethod
    def _response(values: dict[str, Any], *, reused: bool) -> TrainingWorkoutResponse:
        return TrainingWorkoutResponse(
            status=values["status"],
            title=values["title"],
            workout_text=values["workout_text"],
            recovery_note=values.get("recovery_note"),
            recovery_status=values["recovery_status"],
            generated_at=values["created_at"],
            reused=reused,
        )
