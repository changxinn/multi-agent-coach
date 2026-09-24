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
    first_seed = (migration_dir / "003_seed_nutrition_food_cache.sql").read_text(
        encoding="utf-8"
    )
    second_seed = (migration_dir / "004_seed_nutrition_food_cache.sql").read_text(
        encoding="utf-8"
    )

    assert first_seed.count("INSERT INTO nutrition_food_cache (") == 66
    assert second_seed.count("INSERT INTO nutrition_food_cache (") == 67
    assert first_seed.count("'usda', '") == 6_600
    assert second_seed.count("'usda', '") == 6_670
    assert first_seed.count("'usda', '") + second_seed.count("'usda', '") == 13_270
    assert (
        first_seed.count("ON CONFLICT (provider, provider_food_id) DO NOTHING;") == 66
    )
    assert (
        second_seed.count("ON CONFLICT (provider, provider_food_id) DO NOTHING;") == 67
    )
    assert (
        migration_dir / "003_seed_nutrition_food_cache.sql"
    ).stat().st_size < 100_000_000
    assert (
        migration_dir / "004_seed_nutrition_food_cache.sql"
    ).stat().st_size < 100_000_000
    assert "'747429'," not in first_seed + second_seed
    assert "CREATE TABLE" not in first_seed + second_seed


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
