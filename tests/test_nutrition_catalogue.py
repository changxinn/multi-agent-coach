from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from services.nutrition_agent.app.service import NutritionService


@pytest.mark.asyncio
async def test_food_catalogue_delegates_to_unbounded_local_repository():
    db = AsyncMock()
    service = NutritionService(db)
    service.repo.list_all_food_catalogue = AsyncMock(
        return_value=[{"id": 1, "description": "Oats"}]
    )

    result = await service.get_food_catalogue()

    assert result == [{"id": 1, "description": "Oats"}]
    service.repo.list_all_food_catalogue.assert_awaited_once_with()


def test_foundation_catalogue_seed_is_complete_and_idempotent():
    migration = (
        Path(__file__).parents[1]
        / "services/nutrition_agent/app/db/migrations/002_seed_nutrition_foundation_food_cache.sql"
    ).read_text(encoding="utf-8")

    assert migration.count("USDA FoodData Central Foundation bulk export") == 95
    assert migration.count("'usda', '") == 95
    assert "ON CONFLICT (provider, provider_food_id) DO NOTHING;" in migration
    assert "CREATE TABLE" not in migration


def test_imported_food_cache_seeds_are_batched_and_idempotent():
    migration_dir = (
        Path(__file__).parents[1] / "services/nutrition_agent/app/db/migrations"
    )
    seeds = [
        migration_dir / "003_seed_nutrition_food_cache.sql",
        migration_dir / "004_seed_nutrition_food_cache.sql",
        migration_dir / "005_seed_nutrition_food_cache.sql",
    ]
    contents = [seed.read_text(encoding="utf-8") for seed in seeds]

    assert [
        content.count("INSERT INTO nutrition_food_cache (") for content in contents
    ] == [
        37,
        49,
        47,
    ]
    assert [content.count("'usda', '") for content in contents] == [3_700, 4_900, 4_670]
    assert sum(content.count("'usda', '") for content in contents) == 13_270
    assert [
        content.count("ON CONFLICT (provider, provider_food_id) DO NOTHING;")
        for content in contents
    ] == [37, 49, 47]
    assert all(seed.stat().st_size < 50_000_000 for seed in seeds)
    assert "'747429'," not in "".join(contents)
    assert "CREATE TABLE" not in "".join(contents)


def test_private_manual_meal_item_requires_explicit_macros():
    from services.nutrition_agent.app.schemas import MealItem

    with pytest.raises(ValueError, match="Manual estimates require explicit values"):
        MealItem(
            food_name="Soup", quantity=Decimal(1), unit="bowl", calories=Decimal(100)
        )

    item = MealItem(
        food_name="Soup",
        quantity=Decimal(1),
        unit="bowl",
        calories=Decimal(0),
        protein_g=Decimal(0),
        carbohydrate_g=Decimal(0),
        fat_g=Decimal(0),
    )
    assert item.calories == Decimal(0)
