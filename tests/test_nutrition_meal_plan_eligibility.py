from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.nutrition_agent.app.meal_plan_eligibility import (
    contains_alcohol,
    is_eligible_for_meal_plan,
)
from services.nutrition_agent.app.meal_plan_generator import (
    MealPlanGenerationError,
    MealPlanLLMGenerator,
)
from services.nutrition_agent.app.schemas import MealPlanGenerateRequest
from services.nutrition_agent.app.service import NutritionService, _request_ranked_foods


def _food(food_id: int, description: str, alcohol: str | Decimal) -> dict:
    return {
        "id": food_id,
        "description": description,
        "calories_per_100g": Decimal(100),
        "protein_g_per_100g": Decimal(10),
        "carbohydrate_g_per_100g": Decimal(10),
        "fat_g_per_100g": Decimal(5),
        "fiber_g_per_100g": Decimal(2),
        "raw_response": {
            "foodNutrients": [{"name": "Alcohol, ethyl", "amount": alcohol}]
        },
    }


def _target() -> dict:
    return {
        "id": 3,
        "calorie_target_kcal": Decimal(1800),
        "protein_target_g": Decimal(120),
        "carbohydrate_target_g": Decimal(180),
        "fat_target_g": Decimal(60),
        "fiber_target_g": Decimal(30),
    }


def _request() -> MealPlanGenerateRequest:
    return MealPlanGenerateRequest(
        user_id=7,
        start_date="2026-09-22",
        end_date="2026-09-22",
        meal_types=["breakfast"],
    )


def test_alcohol_eligibility_excludes_positive_amount_and_accepts_zero():
    assert contains_alcohol(_food(1, "Wine", "12.5"))
    assert not is_eligible_for_meal_plan(_food(1, "Wine", "12.5"))
    assert not contains_alcohol(_food(2, "Cooking wine, alcohol removed", 0))
    assert is_eligible_for_meal_plan(_food(2, "Cooking wine, alcohol removed", 0))
    assert not contains_alcohol(
        {
            "raw_response": {
                "foodNutrients": [{"name": "Alcohol, ethyl", "amount": "unknown"}]
            }
        }
    )


def test_fallback_food_order_is_request_specific_not_alphabetical():
    foods = [
        {"id": 1, "description": "Apple"},
        {"id": 2, "description": "Banana"},
        {"id": 3, "description": "Carrot"},
    ]

    first_order = _request_ranked_foods(foods, "request-1")
    second_order = _request_ranked_foods(foods, "request-2")

    assert first_order == _request_ranked_foods(foods, "request-1")
    assert [food["id"] for food in first_order] != [1, 2, 3]
    assert [food["id"] for food in first_order] != [food["id"] for food in second_order]


@pytest.mark.asyncio
async def test_llm_catalogue_browse_exposes_only_alcohol_free_foods():
    repo = MagicMock()
    beer = _food(10, "Beer", "4.2")
    oats = _food(11, "Oats", 0)
    repo.browse_food_catalogue = AsyncMock(return_value=([beer, oats], False))
    repo.get_food_safety_metadata = AsyncMock(
        return_value={
            10: {"allergen_status": "known", "allergen_data": []},
            11: {"allergen_status": "known", "allergen_data": []},
        }
    )
    generator = MealPlanLLMGenerator(MagicMock(), repo)
    exposed_ids: set[int] = set()

    result = await generator._browse(
        {"cursor": 0, "limit": 25}, {"allergies": []}, exposed_ids
    )

    assert [food["id"] for food in result["items"]] == [11]
    assert exposed_ids == {11}


@pytest.mark.asyncio
async def test_materializing_an_alcoholic_llm_selection_is_rejected():
    service = NutritionService(AsyncMock())
    wine = _food(10, "Wine", "12.5")
    service.repo.get_food_catalogue_by_ids = AsyncMock(return_value={10: wine})
    service.repo.get_food_safety_metadata = AsyncMock(
        return_value={10: {"allergen_status": "known", "allergen_data": []}}
    )

    with pytest.raises(MealPlanGenerationError, match="not safe"):
        await service._materialize_llm_meals(
            [
                {
                    "planned_date": "2026-09-22",
                    "meal_type": "breakfast",
                    "items": [{"food_cache_id": 10, "grams": 100}],
                }
            ],
            _target(),
            _request(),
        )


@pytest.mark.asyncio
async def test_deterministic_fallback_excludes_positive_alcohol_foods():
    generator = MagicMock()
    generator.generate = AsyncMock(side_effect=MealPlanGenerationError("disabled"))
    service = NutritionService(AsyncMock(), meal_plan_generator=generator)
    beer = _food(10, "Beer", "4.2")
    oats = _food(11, "Oats", 0)
    service.repo.get_active_target = AsyncMock(return_value=_target())
    service.repo.list_food_catalogue = AsyncMock(return_value=[beer, oats])
    service.repo.get_food_safety_metadata = AsyncMock(
        return_value={
            10: {"allergen_status": "known", "allergen_data": []},
            11: {"allergen_status": "known", "allergen_data": []},
        }
    )
    service.repo.get_target_snapshot = AsyncMock(return_value={"id": 3})
    service.repo.create_meal_plan = AsyncMock(return_value={"id": 42})

    await service.generate_meal_plan(7, _request())

    create_args = service.repo.create_meal_plan.await_args.kwargs
    assert create_args["generated_plan"]["catalogue_food_ids"] == [11]
    assert create_args["planned_meals"][0]["items"][0]["food_name"] == "Oats"
