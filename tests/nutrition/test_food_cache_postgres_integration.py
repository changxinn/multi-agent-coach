"""PostgreSQL integration coverage for Nutrition food-cache persistence.

These tests never infer a database target: they run only when the explicitly
configured, fail-closed ``NUTRITION_TEST_DATABASE_URL`` targets
``nutrition_test``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from app.config import get_settings
from app.db.migrate import run_migrations
from app.db.migrate import test_database_url as isolated_test_database_url
from services.nutrition_agent.app.repository import NutritionRepository


class _IntegrationSettings:
    FOOD_CACHE_FRESH_DAYS = 30
    def __init__(self, database_url: str) -> None:
        self.DATABASE_URL = database_url

    @staticmethod
    def validated_schema() -> str:
        return "systemdb"


@pytest.fixture
async def food_cache_repository() -> AsyncIterator[NutritionRepository]:
    """Apply migrations and connect only to the explicit disposable database."""
    try:
        database_url = isolated_test_database_url()
    except RuntimeError as error:
        pytest.skip(str(error))

    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    try:
        result = await run_migrations()
        assert result.compatible, result.reason
        repository = NutritionRepository(_IntegrationSettings(database_url))
        await repository.connect()
        try:
            yield repository
        finally:
            await repository.close()
    finally:
        if original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_database_url
        get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def clear_integration_foods(
    food_cache_repository: NutritionRepository,
) -> AsyncIterator[None]:
    """Keep the disposable database reusable without touching seeded cache rows."""
    first_id, last_id = 9_000_000_000_000, 9_000_000_000_100
    await food_cache_repository._pool.execute(
        'DELETE FROM "systemdb".food_cache WHERE fdc_id BETWEEN $1 AND $2',
        first_id,
        last_id,
    )
    try:
        yield
    finally:
        await food_cache_repository._pool.execute(
            'DELETE FROM "systemdb".food_cache WHERE fdc_id BETWEEN $1 AND $2',
            first_id,
            last_id,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_food_cache_upsert_search_and_suppression_use_migrated_postgres(
    food_cache_repository: NutritionRepository,
) -> None:
    first_id, second_id = 9_000_000_000_001, 9_000_000_000_002
    first = await food_cache_repository.upsert_cached_food(
        {
            "fdc_id": first_id,
            "name": "Integration Cache Apple",
            "brand": "Initial brand",
            "serving_size_g": 100,
            "calories": 52,
            "protein_g": 0.3,
            "carbs_g": 14,
            "fat_g": 0.2,
            "fiber_g": 2.4,
            "category": "fruit",
        }
    )
    second = await food_cache_repository.upsert_cached_food(
        {
            "fdc_id": second_id,
            "name": "Integration Cache Banana",
            "serving_size_g": 118,
            "calories": 105,
            "category": "fruit",
        }
    )

    assert first["source"] == second["source"] == "usda"
    assert first["suppression_until"] is None
    assert first["fetched_at"] <= first["refresh_after"]
    assert timedelta(days=29, hours=23, minutes=59) < (
        first["refresh_after"] - first["fetched_at"]
    ) < timedelta(days=30, minutes=1)

    results = await food_cache_repository.search_food_cache("INTEGRATION CACHE", limit=10)
    assert [item["fdc_id"] for item in results] == [first_id, second_id]

    updated = await food_cache_repository.upsert_cached_food(
        {
            "fdc_id": first_id,
            "name": "Integration Cache Apricot",
            "brand": "Updated brand",
            "serving_size_g": 120,
            "calories": 48,
            "category": "fruit",
        }
    )
    assert updated["name"] == "Integration Cache Apricot"
    assert updated["brand"] == "Updated brand"
    assert updated["calories"] == 48

    suppression_until = datetime.now(UTC) + timedelta(minutes=15)
    await food_cache_repository.suppress_food_refresh(first_id, suppression_until)
    cached = await food_cache_repository.get_cached_food(first_id)
    assert cached is not None
    assert cached["suppression_until"] == suppression_until

    await food_cache_repository.suppress_food_search(
        "integration cache apple", suppression_until, "no_result"
    )
    assert await food_cache_repository.get_food_search_suppression("integration cache apple") == {
        "normalized_query": "integration cache apple",
        "suppression_until": suppression_until,
        "reason": "no_result",
    }