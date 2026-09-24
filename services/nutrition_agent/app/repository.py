"""Database access for the user-owned nutrition domain."""

import json
from datetime import date
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession


class NutritionRepository:
    """Encapsulates nutrition SQL while retaining PostgreSQL JSON semantics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_idempotent_response(
        self, user_id: int, operation: str, key: str
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
                SELECT request_fingerprint, response FROM nutrition_idempotency_keys
                WHERE user_id = :user_id AND operation = :operation AND idempotency_key = :key
            """),
            {"user_id": user_id, "operation": operation, "key": key},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def save_idempotent_response(
        self, user_id: int, operation: str, key: str, fingerprint: str, response: str
    ) -> None:
        await self.db.execute(
            text("""
                INSERT INTO nutrition_idempotency_keys
                    (user_id, operation, idempotency_key, request_fingerprint, response)
                VALUES (:user_id, :operation, :key, :fingerprint, CAST(:response AS jsonb))
            """),
            {
                "user_id": user_id,
                "operation": operation,
                "key": key,
                "fingerprint": fingerprint,
                "response": response,
            },
        )

    async def create_meal_plan(
        self,
        user_id: int,
        target_snapshot_id: int,
        start_date: date,
        end_date: date,
        generated_plan: dict[str, Any],
        safety_warnings: list[str],
        planned_meals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Persist the next immutable plan version and its structured meals.

        The advisory transaction lock serializes version allocation per user without
        preventing other users from creating plans concurrently.
        """
        await self.lock_user_meal_plans(user_id)
        version_result = await self.db.execute(
            text("""
                SELECT COALESCE(MAX(version), 0) + 1
                FROM nutrition_meal_plans
                WHERE user_id = :user_id AND start_date = :start_date
                    AND end_date = :end_date
            """),
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )
        version = version_result.scalar_one()
        result = await self.db.execute(
            text("""
                INSERT INTO nutrition_meal_plans (
                    user_id, target_snapshot_id, start_date, end_date, version,
                    status, generated_plan, safety_warnings
                ) VALUES (
                    :user_id, :target_snapshot_id, :start_date, :end_date, :version,
                    'draft', CAST(:generated_plan AS jsonb), CAST(:safety_warnings AS jsonb)
                ) RETURNING *
            """),
            {
                "user_id": user_id,
                "target_snapshot_id": target_snapshot_id,
                "start_date": start_date,
                "end_date": end_date,
                "version": version,
                "generated_plan": json.dumps(generated_plan, default=str),
                "safety_warnings": json.dumps(safety_warnings),
            },
        )
        plan = dict(result.mappings().one())
        await self._create_planned_meals(plan["id"], planned_meals)
        return plan

    async def lock_user_meal_plans(self, user_id: int) -> None:
        """Serialize plan lifecycle transitions for one user within this transaction."""
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:user_id)"), {"user_id": user_id}
        )

    async def get_meal_plan(
        self, user_id: int, meal_plan_id: int
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
                SELECT p.*, COALESCE(json_agg(json_build_object(
                    'id', pm.id, 'planned_date', pm.planned_date,
                    'meal_type', pm.meal_type,
                    'calorie_target_kcal', pm.calorie_target_kcal,
                    'protein_target_g', pm.protein_target_g,
                    'carbohydrate_target_g', pm.carbohydrate_target_g,
                    'fat_target_g', pm.fat_target_g,
                    'fiber_target_g', pm.fiber_target_g, 'items', pm.items,
                    'safety_status', pm.safety_status,
                    'safety_warnings', pm.safety_warnings
                ) ORDER BY pm.planned_date, pm.meal_type) FILTER (WHERE pm.id IS NOT NULL),
                    '[]'::json) AS planned_meals
                FROM nutrition_meal_plans p
                LEFT JOIN nutrition_planned_meals pm ON pm.meal_plan_id = p.id
                WHERE p.id = :meal_plan_id AND p.user_id = :user_id
                GROUP BY p.id
            """),
            {"user_id": user_id, "meal_plan_id": meal_plan_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_meal_plans(self, user_id: int) -> list[dict[str, Any]]:
        result = await self.db.execute(
            text("""
                SELECT id, target_snapshot_id, start_date, end_date, version, status,
                    generated_plan, safety_warnings, created_at, updated_at
                FROM nutrition_meal_plans WHERE user_id = :user_id
                ORDER BY created_at DESC, id DESC
            """),
            {"user_id": user_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def activate_draft_meal_plan(
        self,
        user_id: int,
        meal_plan_id: int,
        start_date: date,
        end_date: date,
        planned_meals: list[dict[str, Any]],
        safety_warnings: list[str],
    ) -> dict[str, Any] | None:
        for meal in planned_meals:
            await self.db.execute(
                text("""
                UPDATE nutrition_planned_meals
                    SET safety_status = :safety_status,
                        safety_warnings = CAST(:safety_warnings AS jsonb)
                    WHERE id = :id AND meal_plan_id = :meal_plan_id
                """),
                {
                    "id": meal["id"],
                    "meal_plan_id": meal_plan_id,
                    "safety_status": meal["safety_status"],
                    "safety_warnings": json.dumps(meal["safety_warnings"]),
                },
            )
        await self.db.execute(
            text("""
                UPDATE nutrition_meal_plans SET status = 'superseded',
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = :user_id AND status = 'active' AND id != :meal_plan_id
                    AND start_date <= :end_date AND end_date >= :start_date
            """),
            {
                "user_id": user_id,
                "meal_plan_id": meal_plan_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        result = await self.db.execute(
            text("""
                UPDATE nutrition_meal_plans SET status = 'active',
                    safety_warnings = CAST(:safety_warnings AS jsonb), updated_at = CURRENT_TIMESTAMP
                WHERE id = :meal_plan_id AND user_id = :user_id AND status = 'draft'
                RETURNING *
            """),
            {
                "user_id": user_id,
                "meal_plan_id": meal_plan_id,
                "safety_warnings": json.dumps(safety_warnings),
            },
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def archive_meal_plan(
        self, user_id: int, meal_plan_id: int
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
                UPDATE nutrition_meal_plans SET status = 'archived',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :meal_plan_id AND user_id = :user_id
                    AND status IN ('draft', 'active') RETURNING *
            """),
            {"user_id": user_id, "meal_plan_id": meal_plan_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_food_safety_metadata(
        self, food_cache_ids: set[int]
    ) -> dict[int, dict[str, Any]]:
        if not food_cache_ids:
            return {}
        statement = text("""
            SELECT id, allergen_data, allergen_status
            FROM nutrition_food_cache
            WHERE id IN :food_cache_ids
        """).bindparams(bindparam("food_cache_ids", expanding=True))
        result = await self.db.execute(
            statement, {"food_cache_ids": sorted(food_cache_ids)}
        )
        return {row["id"]: dict(row) for row in result.mappings().all()}

    async def get_target_snapshot(
        self, user_id: int, target_snapshot_id: int
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
                SELECT * FROM nutrition_target_snapshots
                WHERE id = :target_snapshot_id AND user_id = :user_id
            """),
            {"user_id": user_id, "target_snapshot_id": target_snapshot_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_active_meal_plan(
        self, user_id: int, for_date: date
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
                SELECT p.*, COALESCE(json_agg(json_build_object(
                    'id', pm.id, 'planned_date', pm.planned_date,
                    'meal_type', pm.meal_type,
                    'calorie_target_kcal', pm.calorie_target_kcal,
                    'protein_target_g', pm.protein_target_g,
                    'carbohydrate_target_g', pm.carbohydrate_target_g,
                    'fat_target_g', pm.fat_target_g,
                    'fiber_target_g', pm.fiber_target_g, 'items', pm.items,
                    'safety_status', pm.safety_status,
                    'safety_warnings', pm.safety_warnings
                ) ORDER BY pm.meal_type) FILTER (WHERE pm.id IS NOT NULL),
                    '[]'::json) AS planned_meals
                FROM nutrition_meal_plans p
                LEFT JOIN nutrition_planned_meals pm
                    ON pm.meal_plan_id = p.id AND pm.planned_date = :for_date
                WHERE p.user_id = :user_id AND p.status = 'active'
                    AND p.start_date <= :for_date AND p.end_date >= :for_date
                GROUP BY p.id
                ORDER BY p.version DESC, p.created_at DESC
                LIMIT 1
            """),
            {"user_id": user_id, "for_date": for_date},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def _create_planned_meals(
        self, meal_plan_id: int, planned_meals: list[dict[str, Any]]
    ) -> None:
        statement = text("""
            INSERT INTO nutrition_planned_meals (
                meal_plan_id, planned_date, meal_type, calorie_target_kcal,
                protein_target_g, carbohydrate_target_g, fat_target_g,
                fiber_target_g, items, safety_status, safety_warnings
            ) VALUES (
                :meal_plan_id, :planned_date, :meal_type, :calorie_target_kcal,
                :protein_target_g, :carbohydrate_target_g, :fat_target_g,
                :fiber_target_g, CAST(:items AS jsonb), :safety_status,
                CAST(:safety_warnings AS jsonb)
            )
        """)
        for meal in planned_meals:
            await self.db.execute(
                statement,
                {
                    "meal_plan_id": meal_plan_id,
                    **meal,
                    "items": json.dumps(meal["items"], default=str),
                    "safety_warnings": json.dumps(meal.get("safety_warnings", [])),
                },
            )

    async def lock_open_target(self, user_id: int) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
                SELECT id, effective_from FROM nutrition_target_snapshots
                WHERE user_id = :user_id AND effective_to IS NULL FOR UPDATE
            """),
            {"user_id": user_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def update_target(
        self, snapshot_id: int, values: dict[str, Any]
    ) -> dict[str, Any]:
        result = await self.db.execute(
            text("""
                UPDATE nutrition_target_snapshots SET
                    bmr_kcal = :bmr, tdee_kcal = :tdee, calorie_target_kcal = :calories,
                    protein_target_g = :protein, carbohydrate_target_g = :carbohydrates,
                    fat_target_g = :fat, fiber_target_g = :fiber,
                    calculation_method = :method,
                    calculation_inputs = CAST(:inputs AS jsonb)
                WHERE id = :snapshot_id RETURNING *
            """),
            {"snapshot_id": snapshot_id, **values},
        )
        return dict(result.mappings().one())
    async def close_target(self, snapshot_id: int, effective_to: date) -> None:
        await self.db.execute(
            text(
                "UPDATE nutrition_target_snapshots "
                "SET effective_to = :effective_to WHERE id = :snapshot_id"
            ),
            {"snapshot_id": snapshot_id, "effective_to": effective_to},
        )

    async def create_target(
        self, user_id: int, effective_from: date, values: dict[str, Any]
    ) -> dict[str, Any]:
        result = await self.db.execute(
            text("""
                INSERT INTO nutrition_target_snapshots (
                    user_id, effective_from, bmr_kcal, tdee_kcal,
                    calorie_target_kcal, protein_target_g, carbohydrate_target_g,
                    fat_target_g, fiber_target_g,
                    calculation_method, calculation_inputs
                ) VALUES (
                    :user_id, :effective_from, :bmr, :tdee, :calories, :protein,
                    :carbohydrates, :fat, :fiber, :method, CAST(:inputs AS jsonb)
                ) RETURNING *
            """),
            {"user_id": user_id, "effective_from": effective_from, **values},
        )
        return dict(result.mappings().one())
    async def get_active_target(self, user_id: int) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
                SELECT * FROM nutrition_target_snapshots
                WHERE user_id = :user_id AND effective_from <= CURRENT_DATE
                    AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
                ORDER BY created_at DESC LIMIT 1
            """),
            {"user_id": user_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_target_for_date(
        self, user_id: int, for_date: date
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
                SELECT * FROM nutrition_target_snapshots
                WHERE user_id = :user_id AND effective_from <= :for_date
                    AND (effective_to IS NULL OR effective_to >= :for_date)
                ORDER BY created_at DESC LIMIT 1
            """),
            {"user_id": user_id, "for_date": for_date},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_cached_food(
        self, provider: str, provider_food_id: str
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
                SELECT * FROM nutrition_food_cache
                WHERE provider = :provider AND provider_food_id = :provider_food_id
            """),
            {"provider": provider, "provider_food_id": provider_food_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_food_catalogue(self, limit: int) -> list[dict[str, Any]]:
        """Return locally cached USDA foods with all values needed by the meal form."""
        result = await self.db.execute(
            text("""
                SELECT id, provider_food_id, description, serving_size_g,
                       serving_description, calories_per_100g, protein_g_per_100g,
                       carbohydrate_g_per_100g, fat_g_per_100g, fiber_g_per_100g,
                       allergen_data, allergen_status
                FROM nutrition_food_cache
                WHERE provider = 'usda'
                  AND calories_per_100g IS NOT NULL
                  AND protein_g_per_100g IS NOT NULL
                  AND carbohydrate_g_per_100g IS NOT NULL
                  AND fat_g_per_100g IS NOT NULL
                ORDER BY description, id
                LIMIT :limit
            """),
            {"limit": limit},
        )
        return [dict(row) for row in result.mappings().all()]

    async def list_all_food_catalogue(self) -> list[dict[str, Any]]:
        """Return every compatible locally cached USDA food for the Meal Log selector."""
        result = await self.db.execute(
            text("""
                SELECT id, provider_food_id, description, serving_size_g,
                       serving_description, calories_per_100g, protein_g_per_100g,
                       carbohydrate_g_per_100g, fat_g_per_100g, fiber_g_per_100g,
                       allergen_data, allergen_status
                FROM nutrition_food_cache
                WHERE provider = 'usda'
                  AND calories_per_100g IS NOT NULL
                  AND protein_g_per_100g IS NOT NULL
                  AND carbohydrate_g_per_100g IS NOT NULL
                  AND fat_g_per_100g IS NOT NULL
                ORDER BY description, id
            """)
        )
        return [dict(row) for row in result.mappings().all()]

    async def cache_food(self, values: dict[str, Any]) -> dict[str, Any]:
        result = await self.db.execute(
            text("""
                INSERT INTO nutrition_food_cache (
                    provider, provider_food_id, description, serving_size_g,
                    serving_description, calories_per_100g, protein_g_per_100g,
                    carbohydrate_g_per_100g, fat_g_per_100g, fiber_g_per_100g,
                    allergen_data, allergen_status, raw_response
                ) VALUES (
                    :provider, :provider_food_id, :description, :serving_size_g,
                    :serving_description, :calories_per_100g, :protein_g_per_100g,
                    :carbohydrate_g_per_100g, :fat_g_per_100g, :fiber_g_per_100g,
                    CAST(:allergen_data AS jsonb), :allergen_status,
                    CAST(:raw_response AS jsonb)
                ) ON CONFLICT (provider, provider_food_id) DO UPDATE SET
                    description = EXCLUDED.description,
                    serving_size_g = EXCLUDED.serving_size_g,
                    serving_description = EXCLUDED.serving_description,
                    calories_per_100g = EXCLUDED.calories_per_100g,
                    protein_g_per_100g = EXCLUDED.protein_g_per_100g,
                    carbohydrate_g_per_100g = EXCLUDED.carbohydrate_g_per_100g,
                    fat_g_per_100g = EXCLUDED.fat_g_per_100g,
                    fiber_g_per_100g = EXCLUDED.fiber_g_per_100g,
                    allergen_data = EXCLUDED.allergen_data,
                    allergen_status = EXCLUDED.allergen_status,
                    raw_response = EXCLUDED.raw_response,
                    fetched_at = CURRENT_TIMESTAMP
                RETURNING *
            """),
            {
                **values,
                "allergen_data": json.dumps(values["allergen_data"]),
                "raw_response": json.dumps(values["raw_response"]),
            },
        )
        return dict(result.mappings().one())
