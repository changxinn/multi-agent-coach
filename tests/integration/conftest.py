"""Live PostgreSQL fixtures for Nutrition Agent persistence tests."""

import hashlib
import os
import sys
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

nutrition_agent_app = ModuleType("nutrition_agent_app")
nutrition_agent_app.__path__ = [
    str(Path(__file__).parents[2] / "services/nutrition_agent/app")
]
sys.modules["nutrition_agent_app"] = nutrition_agent_app


def _integration_database_url() -> str | None:
    """Return an async SQLAlchemy URL only when integration testing is configured."""
    url = os.getenv("NUTRITION_INTEGRATION_DATABASE_URL")
    if not url:
        return None
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.fixture
async def postgres_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = _integration_database_url()
    if not database_url:
        pytest.skip(
            "NUTRITION_INTEGRATION_DATABASE_URL is required for PostgreSQL tests"
        )

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
            from nutrition_agent_app.migrations import split_sql_statements

            schema_migration = (
                Path(__file__).parents[2]
                / "services/nutrition_agent/app/db/migrations/001_create_nutrition_schema.sql"
            )
            content = schema_migration.read_text(encoding="utf-8-sig")
            statements = split_sql_statements(
                " ".join(
                    line.strip()
                    for line in content.splitlines()
                    if line.strip() and not line.strip().startswith("--")
                )
            )
            for statement in statements:
                await connection.execute(text(statement))
    except (SQLAlchemyError, asyncpg.PostgresError) as error:
        await engine.dispose()
        pytest.skip(f"PostgreSQL integration database is unavailable: {error}")

    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_postgres(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    async with postgres_session_factory() as session:
        await session.execute(
            text("""
            TRUNCATE TABLE nutrition_planned_meals, nutrition_meal_plans,
                nutrition_idempotency_keys, nutrition_target_snapshots,
                nutrition_food_cache RESTART IDENTITY CASCADE
        """)
        )
        await session.commit()
    yield
    async with postgres_session_factory() as session:
        await session.execute(
            text("""
            TRUNCATE TABLE nutrition_planned_meals, nutrition_meal_plans,
                nutrition_idempotency_keys, nutrition_target_snapshots,
                nutrition_food_cache RESTART IDENTITY CASCADE
        """)
        )
        await session.commit()


async def create_user(session: AsyncSession, email: str) -> int:
    """Return a stable external user identifier without accessing the main database."""
    del session
    return int.from_bytes(hashlib.sha256(email.encode()).digest()[:8], "big") >> 1


async def create_target(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        text("""
            INSERT INTO nutrition_target_snapshots (
                user_id, effective_from, bmr_kcal, tdee_kcal, calorie_target_kcal,
                protein_target_g, carbohydrate_target_g, fat_target_g, fiber_target_g,
                calculation_method, calculation_inputs
            ) VALUES (
                :user_id, :effective_from, 1400, 2000, 2000, 120, 250, 65, 28,
                'integration_test', '{}'::jsonb
            ) RETURNING id
        """),
        {"user_id": user_id, "effective_from": date(2026, 9, 1)},
    )
    return result.scalar_one()


def planned_meal(food_cache_id: int | None = None) -> dict[str, object]:
    return {
        "planned_date": date(2026, 9, 22),
        "meal_type": "breakfast",
        "calorie_target_kcal": Decimal(500),
        "protein_target_g": Decimal(30),
        "carbohydrate_target_g": Decimal(50),
        "fat_target_g": Decimal(15),
        "fiber_target_g": Decimal(8),
        "items": [
            {
                "food_name": "Oats",
                "quantity": Decimal(50),
                "unit": "g",
                "calories": Decimal(190),
                "protein_g": Decimal(6),
                "carbohydrate_g": Decimal(32),
                "fat_g": Decimal(4),
                "fiber_g": Decimal(5),
                "source": "meal_plan",
                "food_cache_id": food_cache_id,
            }
        ],
    }
