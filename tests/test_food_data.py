from decimal import Decimal

import httpx
import pytest

from app.services.food_data.usda import FoodDataProviderError, UsdaFoodDataCentralProvider


@pytest.mark.asyncio
async def test_usda_maps_food_details_nutrients_per_100g():
    payload = {
        "fdcId": 123,
        "description": "Test food",
        "servingSize": 28,
        "foodNutrients": [
            {"nutrient": {"name": "Energy"}, "amount": 200},
            {"nutrient": {"name": "Protein"}, "amount": 10},
        ],
    }
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    provider = UsdaFoodDataCentralProvider("key", client)

    food = await provider.get_food_details("123")

    assert food.calories_per_100g == Decimal("200")
    assert food.protein_g_per_100g == Decimal("10")
    assert food.allergen_status == "unknown"
    await client.aclose()


@pytest.mark.asyncio
async def test_usda_unconfigured_key_fails_safely():
    with pytest.raises(FoodDataProviderError, match="not configured"):
        await UsdaFoodDataCentralProvider("").search_foods("oats")