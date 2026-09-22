"""Database access for the user-owned nutrition domain."""

import json
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class NutritionRepository:
    """Encapsulates nutrition SQL while retaining PostgreSQL JSON semantics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, user_id: int) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("SELECT * FROM systemdb.nutrition_profiles WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def upsert_profile(
        self, user_id: int, values: dict[str, Any]
    ) -> dict[str, Any]:
        values = {
            **values,
            "dietary_preferences": [],
            "dietary_restrictions": [],
        }
        result = await self.db.execute(
            text("""
                INSERT INTO systemdb.nutrition_profiles (
                    user_id, sex_for_energy_equation, activity_level,
                    nutrition_goal,
                    dietary_preferences, dietary_restrictions, allergies
                ) VALUES (
                    :user_id, :sex_for_energy_equation, :activity_level,
                    :nutrition_goal, CAST(:dietary_preferences AS jsonb),
                    CAST(:dietary_restrictions AS jsonb),
                    CAST(:allergies AS jsonb)
                ) ON CONFLICT (user_id) DO UPDATE SET
                    sex_for_energy_equation = EXCLUDED.sex_for_energy_equation,
                    activity_level = EXCLUDED.activity_level,
                    nutrition_goal = EXCLUDED.nutrition_goal,
                    dietary_preferences = EXCLUDED.dietary_preferences,
                    dietary_restrictions = EXCLUDED.dietary_restrictions,
                    allergies = EXCLUDED.allergies, updated_at = CURRENT_TIMESTAMP
                RETURNING *
            """),
            {
                "user_id": user_id,
                **{
                    k: json.dumps(v) if isinstance(v, list) else v
                    for k, v in values.items()
                },
            },
        )
        return dict(result.mappings().one())

    async def get_profile_with_measurements(
        self, user_id: int
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
                SELECT np.sex_for_energy_equation, np.activity_level, np.nutrition_goal,
                       np.dietary_preferences, np.dietary_restrictions, np.allergies,
                       fp.age, fp.weight_kg, fp.height_cm
                FROM systemdb.nutrition_profiles np
                LEFT JOIN systemdb.user_fitness_profiles fp ON fp.user_id = np.user_id
                WHERE np.user_id = :user_id
            """),
            {"user_id": user_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def lock_open_target(self, user_id: int) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
                SELECT id, effective_from FROM systemdb.nutrition_target_snapshots
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
                UPDATE systemdb.nutrition_target_snapshots SET
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
                "UPDATE systemdb.nutrition_target_snapshots "
                "SET effective_to = :effective_to WHERE id = :snapshot_id"
            ),
            {"snapshot_id": snapshot_id, "effective_to": effective_to},
        )

    async def create_target(
        self, user_id: int, effective_from: date, values: dict[str, Any]
    ) -> dict[str, Any]:
        result = await self.db.execute(
            text("""
                INSERT INTO systemdb.nutrition_target_snapshots (
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
                SELECT * FROM systemdb.nutrition_target_snapshots
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
                SELECT * FROM systemdb.nutrition_target_snapshots
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
                SELECT * FROM systemdb.nutrition_food_cache
                WHERE provider = :provider AND provider_food_id = :provider_food_id
            """),
            {"provider": provider, "provider_food_id": provider_food_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def cache_food(self, values: dict[str, Any]) -> dict[str, Any]:
        result = await self.db.execute(
            text("""
                INSERT INTO systemdb.nutrition_food_cache (
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

    async def upsert_daily_summary(
        self, user_id: int, for_date: date, values: dict[str, Any]
    ) -> dict[str, Any]:
        result = await self.db.execute(
            text("""
                INSERT INTO systemdb.nutrition_daily_summaries (
                    user_id, summary_date, target_snapshot_id, calories, protein_g,
                    carbohydrate_g, fat_g, fiber_g, meal_count, calorie_adherence_pct,
                    protein_adherence_pct, plan_adherence_pct
                ) VALUES (
                    :user_id, :summary_date, :target_snapshot_id, :calories, :protein_g,
                    :carbohydrate_g, :fat_g, :fiber_g, :meal_count, :calorie_adherence_pct,
                    :protein_adherence_pct, :plan_adherence_pct
                ) ON CONFLICT (user_id, summary_date) DO UPDATE SET
                    target_snapshot_id = EXCLUDED.target_snapshot_id,
                    calories = EXCLUDED.calories, protein_g = EXCLUDED.protein_g,
                    carbohydrate_g = EXCLUDED.carbohydrate_g, fat_g = EXCLUDED.fat_g,
                    fiber_g = EXCLUDED.fiber_g, meal_count = EXCLUDED.meal_count,
                    calorie_adherence_pct = EXCLUDED.calorie_adherence_pct,
                    protein_adherence_pct = EXCLUDED.protein_adherence_pct,
                    plan_adherence_pct = EXCLUDED.plan_adherence_pct,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING *
            """),
            {"user_id": user_id, "summary_date": for_date, **values},
        )
        return dict(result.mappings().one())

    async def create_meal(
        self, user_id: int, meal: dict[str, Any], items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        result = await self.db.execute(
            text("""
            INSERT INTO systemdb.nutrition_meals (user_id, eaten_at, meal_type, notes)
            VALUES (:user_id, :eaten_at, :meal_type, :notes) RETURNING *
        """),
            {"user_id": user_id, **meal},
        )
        record = dict(result.mappings().one())
        await self._create_items(record["id"], items)
        return record

    async def list_meals(self, user_id: int, for_date: date) -> list[dict[str, Any]]:
        start = datetime.combine(for_date, time.min, tzinfo=UTC)
        end = datetime.combine(for_date, time.max, tzinfo=UTC)
        result = await self.db.execute(
            text("""
            SELECT m.*, COALESCE(json_agg(json_build_object(
                'id', i.id, 'food_name', i.food_name, 'quantity', i.quantity,
                'unit', i.unit, 'grams', i.grams, 'calories', i.calories,
                'protein_g', i.protein_g, 'carbohydrate_g', i.carbohydrate_g,
                'fat_g', i.fat_g, 'fiber_g', i.fiber_g, 'source', i.source,
                'food_cache_id', i.food_cache_id
            )) FILTER (WHERE i.id IS NOT NULL), '[]'::json) AS items
            FROM systemdb.nutrition_meals m
            LEFT JOIN systemdb.nutrition_meal_items i ON i.meal_id = m.id
            WHERE m.user_id = :user_id AND m.eaten_at BETWEEN :start AND :end
            GROUP BY m.id ORDER BY m.eaten_at
        """),
            {"user_id": user_id, "start": start, "end": end},
        )
        return [dict(row) for row in result.mappings()]

    async def replace_meal(
        self,
        user_id: int,
        meal_id: int,
        meal: dict[str, Any],
        items: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        result = await self.db.execute(
            text("""
            UPDATE systemdb.nutrition_meals
            SET eaten_at = :eaten_at, meal_type = :meal_type, notes = :notes
            WHERE id = :meal_id AND user_id = :user_id RETURNING *
        """),
            {"user_id": user_id, "meal_id": meal_id, **meal},
        )
        record = result.mappings().first()
        if record is None:
            return None
        await self.db.execute(
            text("DELETE FROM systemdb.nutrition_meal_items WHERE meal_id = :meal_id"),
            {"meal_id": meal_id},
        )
        await self._create_items(meal_id, items)
        return dict(record)

    async def delete_meal(self, user_id: int, meal_id: int) -> bool:
        result = await self.db.execute(
            text("""
            DELETE FROM systemdb.nutrition_meals
            WHERE id = :meal_id AND user_id = :user_id
            RETURNING id
        """),
            {"user_id": user_id, "meal_id": meal_id},
        )
        return result.scalar_one_or_none() is not None

    async def get_daily_totals(self, user_id: int, for_date: date) -> dict[str, Any]:
        start = datetime.combine(for_date, time.min, tzinfo=UTC)
        end = datetime.combine(for_date, time.max, tzinfo=UTC)
        result = await self.db.execute(
            text("""
            SELECT COUNT(DISTINCT m.id) AS meal_count,
                COALESCE(SUM(i.calories), 0) AS calories,
                COALESCE(SUM(i.protein_g), 0) AS protein_g,
                COALESCE(SUM(i.carbohydrate_g), 0) AS carbohydrate_g,
                COALESCE(SUM(i.fat_g), 0) AS fat_g,
                COALESCE(SUM(i.fiber_g), 0) AS fiber_g
            FROM systemdb.nutrition_meals m
            LEFT JOIN systemdb.nutrition_meal_items i ON i.meal_id = m.id
            WHERE m.user_id = :user_id AND m.eaten_at BETWEEN :start AND :end
        """),
            {"user_id": user_id, "start": start, "end": end},
        )
        return dict(result.mappings().one())

    async def _create_items(self, meal_id: int, items: list[dict[str, Any]]) -> None:
        statement = text("""
            INSERT INTO systemdb.nutrition_meal_items (
                meal_id, food_name, quantity, unit, grams, calories, protein_g,
                carbohydrate_g, fat_g, fiber_g, source, food_cache_id
            ) VALUES (:meal_id, :food_name, :quantity, :unit, :grams, :calories,
                :protein_g, :carbohydrate_g, :fat_g, :fiber_g, :source, :food_cache_id)
        """)
        for item in items:
            await self.db.execute(statement, {"meal_id": meal_id, **item})
