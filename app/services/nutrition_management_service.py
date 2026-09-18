"""Direct, user-scoped persistence for the Nutrition Management API."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.nutrition_management import (
    MealWriteRequest,
    ProfileWriteRequest,
    TargetCalculateRequest,
)
from services.nutrition_agent.app.assessment import (
    POLICY_VERSION,
    escalation_for,
    safety_findings,
)
from services.nutrition_agent.app.tools.macro_targets import calculate_macro_targets
from services.nutrition_agent.app.tools.tdee_calculator import calculate_tdee


class NutritionManagementNotFound(Exception):
    """Resource was absent or does not belong to the current user."""


def _record(row: Any) -> dict[str, Any]:
    value = dict(row)
    for key, item in value.items():
        if hasattr(item, "as_tuple"):
            value[key] = float(item)
        elif isinstance(item, str) and key in {"dietary_restrictions", "allergies", "inputs", "macro_targets", "recommendations", "safety_projection"}:
            value[key] = json.loads(item)
    return value


class NutritionManagementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def profile(self, user_id: int) -> dict[str, Any]:
        row = (await self.db.execute(text("SELECT user_id, timezone, dietary_preference, dietary_restrictions, allergies, meals_per_day, activity_level, age, gender, weight_kg, height_cm, created_at, updated_at FROM systemdb.nutrition_profiles WHERE user_id = :user_id"), {"user_id": user_id})).mappings().first()
        if not row:
            raise NutritionManagementNotFound
        return _record(row)

    async def save_profile(self, user_id: int, payload: ProfileWriteRequest) -> dict[str, Any]:
        values = payload.model_dump(mode="json")
        row = (await self.db.execute(text("""INSERT INTO systemdb.nutrition_profiles (user_id, timezone, dietary_preference, dietary_restrictions, allergies, meals_per_day, activity_level, age, gender, weight_kg, height_cm, updated_at) VALUES (:user_id, :timezone, :dietary_preference, CAST(:dietary_restrictions AS jsonb), CAST(:allergies AS jsonb), :meals_per_day, :activity_level, :age, :gender, :weight_kg, :height_cm, CURRENT_TIMESTAMP) ON CONFLICT (user_id) DO UPDATE SET timezone = EXCLUDED.timezone, dietary_preference = EXCLUDED.dietary_preference, dietary_restrictions = EXCLUDED.dietary_restrictions, allergies = EXCLUDED.allergies, meals_per_day = EXCLUDED.meals_per_day, activity_level = EXCLUDED.activity_level, age = EXCLUDED.age, gender = EXCLUDED.gender, weight_kg = EXCLUDED.weight_kg, height_cm = EXCLUDED.height_cm, updated_at = CURRENT_TIMESTAMP RETURNING user_id, timezone, dietary_preference, dietary_restrictions, allergies, meals_per_day, activity_level, age, gender, weight_kg, height_cm, created_at, updated_at"""), {**values, "user_id": user_id, "dietary_restrictions": json.dumps(values["dietary_restrictions"]), "allergies": json.dumps(values["allergies"])})).mappings().one()
        return _record(row)

    async def create_meal(self, user_id: int, payload: MealWriteRequest) -> dict[str, Any]:
        values = payload.model_dump()
        row = (await self.db.execute(text("""INSERT INTO systemdb.meal_logs (user_id, meal_type, description, calories, protein_g, carbs_g, fat_g, logged_at) VALUES (:user_id, :meal_type, :description, :calories, :protein_g, :carbs_g, :fat_g, COALESCE(:logged_at, CURRENT_TIMESTAMP)) RETURNING *"""), {**values, "user_id": user_id})).mappings().one()
        return _record(row)

    async def meal(self, user_id: int, meal_id: int) -> dict[str, Any]:
        row = (await self.db.execute(text("SELECT * FROM systemdb.meal_logs WHERE user_id = :user_id AND id = :id"), {"user_id": user_id, "id": meal_id})).mappings().first()
        if not row:
            raise NutritionManagementNotFound
        return _record(row)

    async def update_meal(self, user_id: int, meal_id: int, payload: MealWriteRequest) -> dict[str, Any]:
        values = payload.model_dump()
        row = (await self.db.execute(text("""UPDATE systemdb.meal_logs SET meal_type = :meal_type, description = :description, calories = :calories, protein_g = :protein_g, carbs_g = :carbs_g, fat_g = :fat_g, logged_at = COALESCE(:logged_at, logged_at), updated_at = CURRENT_TIMESTAMP WHERE user_id = :user_id AND id = :id RETURNING *"""), {**values, "user_id": user_id, "id": meal_id})).mappings().first()
        if not row:
            raise NutritionManagementNotFound
        return _record(row)

    async def delete_meal(self, user_id: int, meal_id: int) -> None:
        result = await self.db.execute(text("DELETE FROM systemdb.meal_logs WHERE user_id = :user_id AND id = :id"), {"user_id": user_id, "id": meal_id})
        if result.rowcount != 1:
            raise NutritionManagementNotFound

    async def list_meals(self, user_id: int, limit: int, offset: int, start_date: date | None = None, end_date: date | None = None, timezone: str = "Asia/Singapore") -> dict[str, Any]:
        clause = ""
        params: dict[str, Any] = {"user_id": user_id, "limit": limit, "offset": offset}
        if start_date and end_date:
            clause = " AND logged_at >= (CAST(:start_date AS date)::timestamp AT TIME ZONE :timezone) AND logged_at < ((CAST(:end_date AS date) + 1)::timestamp AT TIME ZONE :timezone)"
            params.update(start_date=start_date, end_date=end_date, timezone=timezone)
        rows = (await self.db.execute(text(f"SELECT * FROM systemdb.meal_logs WHERE user_id = :user_id{clause} ORDER BY logged_at DESC, id DESC LIMIT :limit OFFSET :offset"), params)).mappings().all()
        total = (await self.db.execute(text(f"SELECT count(*) FROM systemdb.meal_logs WHERE user_id = :user_id{clause}"), params)).scalar_one()
        return {"items": [_record(row) for row in rows], "limit": limit, "offset": offset, "total": total}

    async def foods(self, query: str, limit: int) -> list[dict[str, Any]]:
        rows = (await self.db.execute(text("SELECT fdc_id, name, brand, serving_size_g, calories, protein_g, carbs_g, fat_g, fiber_g, category, last_updated FROM systemdb.food_cache WHERE lower(name) LIKE :query OR lower(COALESCE(brand, '')) LIKE :query ORDER BY name, fdc_id LIMIT :limit"), {"query": f"%{query.strip().lower()}%", "limit": limit})).mappings().all()
        return [_record(row) for row in rows]

    def calculate_target(self, payload: TargetCalculateRequest) -> dict[str, Any]:
        inputs = payload.inputs
        findings = safety_findings("", inputs.safety_context, inputs)
        referral = escalation_for(findings)
        if referral:
            raise ValueError(referral.message)
        expenditure = calculate_tdee(inputs.age, inputs.gender, inputs.weight_kg, inputs.height_cm, inputs.activity_level)
        macros = calculate_macro_targets(expenditure["tdee"], inputs.weight_kg, inputs.fitness_goal, inputs.gender)
        calories = macros.pop("calories")
        findings = safety_findings("", inputs.safety_context, inputs, calories)
        referral = escalation_for(findings)
        if referral:
            raise ValueError(referral.message)
        return {"bmr": expenditure["bmr"], "tdee": expenditure["tdee"], "recommended_calories": calories, "macro_targets": macros, "safety_findings": [finding.model_dump() for finding in findings], "policy_version": POLICY_VERSION}

    async def save_target(self, user_id: int, payload: TargetCalculateRequest, effective_from: date) -> dict[str, Any]:
        calculation = self.calculate_target(payload)
        await self.db.execute(text("SELECT pg_advisory_xact_lock(:user_id)"), {"user_id": user_id})
        await self.db.execute(text("""UPDATE systemdb.nutrition_targets AS target SET effective_to = :effective_from - 1 WHERE target.user_id = :user_id AND target.effective_from < :effective_from AND (target.effective_to IS NULL OR target.effective_to >= :effective_from) AND NOT EXISTS (SELECT 1 FROM systemdb.nutrition_targets AS revision WHERE revision.user_id = target.user_id AND revision.effective_from = target.effective_from AND revision.version > target.version)"""), {"user_id": user_id, "effective_from": effective_from})
        row = (await self.db.execute(text("""INSERT INTO systemdb.nutrition_targets (user_id, inputs, recommended_calories, macro_targets, policy_version, effective_from, effective_to, version) VALUES (:user_id, CAST(:inputs AS jsonb), :recommended_calories, CAST(:macro_targets AS jsonb), :policy_version, :effective_from, (SELECT min(effective_from) - 1 FROM systemdb.nutrition_targets WHERE user_id = :user_id AND effective_from > :effective_from), COALESCE((SELECT max(version) + 1 FROM systemdb.nutrition_targets WHERE user_id = :user_id AND effective_from = :effective_from), 1)) RETURNING *"""), {"user_id": user_id, "inputs": json.dumps(payload.inputs.model_dump(mode="json")), "recommended_calories": calculation["recommended_calories"], "macro_targets": json.dumps(calculation["macro_targets"]), "policy_version": calculation["policy_version"], "effective_from": effective_from})).mappings().one()
        return _record(row)

    async def current_target(self, user_id: int, on_date: date | None) -> dict[str, Any]:
        if on_date is None:
            row = (await self.db.execute(text("SELECT timezone FROM systemdb.nutrition_profiles WHERE user_id = :user_id"), {"user_id": user_id})).mappings().first()
            on_date = datetime.now(ZoneInfo(row["timezone"] if row else "Asia/Singapore")).date()
        row = (await self.db.execute(text("SELECT * FROM systemdb.nutrition_targets WHERE user_id = :user_id AND effective_from <= :on_date AND (effective_to IS NULL OR effective_to >= :on_date) ORDER BY effective_from DESC, version DESC LIMIT 1"), {"user_id": user_id, "on_date": on_date})).mappings().first()
        if not row:
            raise NutritionManagementNotFound
        return _record(row)

    async def history(self, user_id: int, start_date: date, end_date: date, timezone: str) -> dict[str, Any]:
        rows = (await self.db.execute(text("""WITH calendar AS (SELECT generate_series(CAST(:start_date AS date), CAST(:end_date AS date), interval '1 day')::date AS day), daily_logs AS (SELECT (logged_at AT TIME ZONE :timezone)::date AS day, count(*) AS meal_logs, sum(calories) AS calories, sum(protein_g) AS protein_g, sum(carbs_g) AS carbs_g, sum(fat_g) AS fat_g FROM systemdb.meal_logs WHERE user_id = :user_id AND logged_at >= (CAST(:start_date AS date)::timestamp AT TIME ZONE :timezone) AND logged_at < ((CAST(:end_date AS date) + 1)::timestamp AT TIME ZONE :timezone) GROUP BY 1) SELECT calendar.day, COALESCE(daily_logs.meal_logs, 0) AS meal_logs, daily_logs.calories, daily_logs.protein_g, daily_logs.carbs_g, daily_logs.fat_g, target.recommended_calories AS target_calories FROM calendar LEFT JOIN daily_logs USING (day) LEFT JOIN LATERAL (SELECT recommended_calories FROM systemdb.nutrition_targets WHERE user_id = :user_id AND effective_from <= calendar.day AND (effective_to IS NULL OR effective_to >= calendar.day) ORDER BY effective_from DESC, version DESC LIMIT 1) target ON true ORDER BY calendar.day"""), {"user_id": user_id, "start_date": start_date, "end_date": end_date, "timezone": timezone})).mappings().all()
        days = [_record(row) for row in rows]
        logged = [day for day in days if day["meal_logs"]]
        averages = {f"average_daily_{key}": round(sum(float(day[key]) for day in logged if day[key] is not None) / sum(day[key] is not None for day in logged), 1) if any(day[key] is not None for day in logged) else None for key in ("calories", "protein_g", "carbs_g", "fat_g")}
        return {"start_date": start_date, "end_date": end_date, "timezone": timezone, "days_with_logs": len(logged), "days": days, **averages}

    async def assessments(self, user_id: int, limit: int, offset: int) -> dict[str, Any]:
        rows = (await self.db.execute(text("SELECT id, status, score, tdee, macro_targets, presentation_message, recommendations, safety_projection, COALESCE(policy_version, 'nutrition-safety-v1') AS policy_version, created_at FROM systemdb.nutrition_assessments WHERE user_id = :user_id ORDER BY created_at DESC NULLS LAST, id DESC LIMIT :limit OFFSET :offset"), {"user_id": user_id, "limit": limit, "offset": offset})).mappings().all()
        items = []
        for row in rows:
            value = _record(row)
            safety = value.pop("safety_projection") or {}
            items.append({"id": value["id"], "status": value["status"], "score": value["score"], "tdee": value["tdee"], "macro_targets": value["macro_targets"], "message": value.pop("presentation_message"), "recommendations": value["recommendations"], "safety_findings": safety.get("findings", []), "policy_version": value["policy_version"], "created_at": value["created_at"]})
        total = (await self.db.execute(text("SELECT count(*) FROM systemdb.nutrition_assessments WHERE user_id = :user_id"), {"user_id": user_id})).scalar_one()
        return {"items": items, "limit": limit, "offset": offset, "total": total}