"""PostgreSQL repository for the Nutrition Agent service."""
from __future__ import annotations

import json
from datetime import datetime

import asyncpg

from .assessment import NutritionHistory
from .config import Settings
from .schemas import (
    MealLogCreate,
    MealLogResponse,
    NutritionEvaluateResponse,
    NutritionHistoryResponse,
    NutritionProfileCreate,
    NutritionProfileResponse,
)


class NutritionRepository:
    """PostgreSQL repository for nutrition data."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Establish database connection pool."""
        database_url = self.settings.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql://"
        )
        self.pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
        await self.ensure_schema()

    async def close(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()

    @property
    def _pool(self) -> asyncpg.Pool:
        if not self.pool:
            raise RuntimeError("Nutrition repository is not connected")
        return self.pool

    async def ensure_schema(self) -> None:
        """Ensure database schema and tables exist."""
        schema = self.settings.validated_schema()
        async with self._pool.acquire() as conn:
            await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')

            # Nutrition profiles table
            await conn.execute(
                f'''CREATE TABLE IF NOT EXISTS "{schema}".nutrition_profiles (
                    user_id BIGINT PRIMARY KEY REFERENCES "{schema}".users(id) ON DELETE CASCADE,
                    dietary_preference VARCHAR(50) DEFAULT 'omnivore',
                    dietary_restrictions JSONB DEFAULT '[]',
                    allergies JSONB DEFAULT '[]',
                    meals_per_day INTEGER DEFAULT 3,
                    target_calories INTEGER,
                    activity_level VARCHAR(20),
                    age INTEGER,
                    gender VARCHAR(10),
                    weight_kg NUMERIC(5,2),
                    height_cm NUMERIC(5,2),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )'''
            )

            # Meal logs table
            await conn.execute(
                f'''CREATE TABLE IF NOT EXISTS "{schema}".meal_logs (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES "{schema}".users(id) ON DELETE CASCADE,
                    meal_type VARCHAR(20) NOT NULL,
                    description TEXT NOT NULL,
                    calories INTEGER,
                    protein_g NUMERIC(5,2),
                    carbs_g NUMERIC(5,2),
                    fat_g NUMERIC(5,2),
                    logged_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )'''
            )

            # Nutrition assessments table
            await conn.execute(
                f'''CREATE TABLE IF NOT EXISTS "{schema}".nutrition_assessments (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES "{schema}".users(id) ON DELETE CASCADE,
                    status VARCHAR(16) NOT NULL,
                    score INTEGER NOT NULL,
                    tdee INTEGER,
                    macro_targets JSONB,
                    response JSONB NOT NULL,
                    tool_trace JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )'''
            )

            # Food cache table
            await conn.execute(
                f'''CREATE TABLE IF NOT EXISTS "{schema}".food_cache (
                    fdc_id BIGINT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    brand VARCHAR(255),
                    serving_size_g INTEGER,
                    calories NUMERIC(8,2),
                    protein_g NUMERIC(6,2),
                    carbs_g NUMERIC(6,2),
                    fat_g NUMERIC(6,2),
                    fiber_g NUMERIC(6,2),
                    category VARCHAR(50),
                    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )'''
            )

            # Create indexes
            await conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_nutrition_profiles_user_id ON "{schema}".nutrition_profiles(user_id)'
            )
            await conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_meal_logs_user_date ON "{schema}".meal_logs(user_id, logged_at DESC)'
            )
            await conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_nutrition_assessments_user_created ON "{schema}".nutrition_assessments(user_id, created_at DESC)'
            )
            await conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_food_cache_category ON "{schema}".food_cache(category)'
            )
            await conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_food_cache_name ON "{schema}".food_cache(name)'
            )

    async def create_or_update_profile(
        self, payload: NutritionProfileCreate
    ) -> NutritionProfileResponse:
        """Create or update nutrition profile."""
        schema = self.settings.validated_schema()
        row = await self._pool.fetchrow(
            f'''INSERT INTO "{schema}".nutrition_profiles 
                (user_id, dietary_preference, dietary_restrictions, allergies, 
                 meals_per_day, target_calories, activity_level, age, gender, 
                 weight_kg, height_cm, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET
                    dietary_preference = EXCLUDED.dietary_preference,
                    dietary_restrictions = EXCLUDED.dietary_restrictions,
                    allergies = EXCLUDED.allergies,
                    meals_per_day = EXCLUDED.meals_per_day,
                    target_calories = EXCLUDED.target_calories,
                    activity_level = EXCLUDED.activity_level,
                    age = EXCLUDED.age,
                    gender = EXCLUDED.gender,
                    weight_kg = EXCLUDED.weight_kg,
                    height_cm = EXCLUDED.height_cm,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING *''',
            payload.user_id,
            payload.dietary_preference,
            json.dumps(payload.dietary_restrictions),
            json.dumps(payload.allergies),
            payload.meals_per_day,
            payload.target_calories,
            payload.activity_level,
            payload.age,
            payload.gender,
            payload.weight_kg,
            payload.height_cm,
        )
        return NutritionProfileResponse(**dict(row))

    async def get_profile(self, user_id: int) -> NutritionProfileResponse | None:
        """Get nutrition profile by user ID."""
        schema = self.settings.validated_schema()
        row = await self._pool.fetchrow(
            f'SELECT * FROM "{schema}".nutrition_profiles WHERE user_id = $1',
            user_id,
        )
        return NutritionProfileResponse(**dict(row)) if row else None

    async def create_meal_log(self, payload: MealLogCreate) -> MealLogResponse:
        """Log a meal."""
        schema = self.settings.validated_schema()
        row = await self._pool.fetchrow(
            f'''INSERT INTO "{schema}".meal_logs 
                (user_id, meal_type, description, calories, protein_g, carbs_g, fat_g)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id, user_id, meal_type, description, calories, 
                         protein_g, carbs_g, fat_g, logged_at''',
            payload.user_id,
            payload.meal_type,
            payload.description,
            payload.calories,
            payload.protein_g,
            payload.carbs_g,
            payload.fat_g,
        )
        return MealLogResponse(**dict(row))

    async def get_history(self, user_id: int) -> NutritionHistory:
        """Get 7-day nutrition history."""
        schema = self.settings.validated_schema()
        row = await self._pool.fetchrow(
            f'''SELECT
                (SELECT COUNT(*) FROM "{schema}".meal_logs 
                 WHERE user_id = $1 AND logged_at >= NOW() - INTERVAL '7 days') AS meal_logs,
                (SELECT AVG(calories) FROM "{schema}".meal_logs 
                 WHERE user_id = $1 AND logged_at >= NOW() - INTERVAL '7 days') AS avg_calories,
                (SELECT AVG(protein_g) FROM "{schema}".meal_logs 
                 WHERE user_id = $1 AND logged_at >= NOW() - INTERVAL '7 days') AS avg_protein,
                (SELECT AVG(carbs_g) FROM "{schema}".meal_logs 
                 WHERE user_id = $1 AND logged_at >= NOW() - INTERVAL '7 days') AS avg_carbs,
                (SELECT AVG(fat_g) FROM "{schema}".meal_logs 
                 WHERE user_id = $1 AND logged_at >= NOW() - INTERVAL '7 days') AS avg_fat''',
            user_id,
        )

        return NutritionHistory(
            meal_logs_last_7_days=int(row["meal_logs"] or 0),
            average_calories=float(row["avg_calories"]) if row["avg_calories"] else None,
            average_protein_g=float(row["avg_protein"]) if row["avg_protein"] else None,
            average_carbs_g=float(row["avg_carbs"]) if row["avg_carbs"] else None,
            average_fat_g=float(row["avg_fat"]) if row["avg_fat"] else None,
        )

    async def save_assessment(
        self, user_id: int, assessment: NutritionEvaluateResponse
    ) -> None:
        """Save nutrition assessment to database."""
        schema = self.settings.validated_schema()
        await self._pool.execute(
            f'''INSERT INTO "{schema}".nutrition_assessments 
                (user_id, status, score, tdee, macro_targets, response, tool_trace)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb)''',
            user_id,
            assessment.status,
            assessment.score,
            assessment.tdee,
            json.dumps(assessment.macro_targets) if assessment.macro_targets else None,
            assessment.model_dump_json(),
            json.dumps(assessment.tool_trace),
        )

    async def search_food_cache(
        self, query: str, limit: int = 10
    ) -> list[dict]:
        """Search food cache by name."""
        schema = self.settings.validated_schema()
        rows = await self._pool.fetch(
            f'''SELECT fdc_id, name, brand, serving_size_g, calories, 
                       protein_g, carbs_g, fat_g, fiber_g, category
                FROM "{schema}".food_cache
                WHERE name ILIKE $1
                ORDER BY name
                LIMIT $2''',
            f"%{query}%",
            limit,
        )
        return [dict(row) for row in rows]

    async def get_cached_food(self, fdc_id: int) -> dict | None:
        """Get food from cache by FDC ID."""
        schema = self.settings.validated_schema()
        row = await self._pool.fetchrow(
            f'SELECT * FROM "{schema}".food_cache WHERE fdc_id = $1',
            fdc_id,
        )
        return dict(row) if row else None
