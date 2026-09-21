from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from services.nutrition_agent.app.service import NutritionService
from services.nutrition_agent.app.food_data.usda import UsdaFoodDataCentralProvider


@pytest.mark.asyncio
async def test_food_catalogue_delegates_to_local_repository():
    db = AsyncMock()
    service = NutritionService(db)
    service.repo.list_food_catalogue = AsyncMock(return_value=[{"id": 1, "description": "Oats"}])

    result = await service.get_food_catalogue(200)

    assert result == [{"id": 1, "description": "Oats"}]
    service.repo.list_food_catalogue.assert_awaited_once_with(200)


def test_private_manual_meal_item_requires_explicit_macros():
    from services.nutrition_agent.app.schemas import MealItem

    with pytest.raises(ValueError, match="Manual estimates require explicit values"):
        MealItem(food_name="Soup", quantity=Decimal("1"), unit="bowl", calories=Decimal("100"))

    item = MealItem(
        food_name="Soup", quantity=Decimal("1"), unit="bowl", calories=Decimal("0"),
        protein_g=Decimal("0"), carbohydrate_g=Decimal("0"), fat_g=Decimal("0"),
    )
    assert item.calories == Decimal("0")


def test_usda_list_response_maps_top_level_nutrient_names():
    """The importer consumes /foods/list, whose nutrient names are not nested."""
    nutrients = UsdaFoodDataCentralProvider._nutrients({
        "foodNutrients": [
            {"name": "Energy", "amount": 200},
            {"name": "Protein", "amount": 10},
            {"name": "Carbohydrate, by difference", "amount": 20},
            {"name": "Total lipid (fat)", "amount": 5},
        ],
    })

    assert nutrients["Energy"] == Decimal("200")
    assert nutrients["Protein"] == Decimal("10")
    assert nutrients["Carbohydrate, by difference"] == Decimal("20")
    assert nutrients["Total lipid (fat)"] == Decimal("5")