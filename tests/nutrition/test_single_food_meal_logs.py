"""Meal logs contain one food, independently of the food's source."""

import pytest
from pydantic import ValidationError

from app.api.schemas.nutrition import MealInput
from services.nutrition_agent.app.schemas import MealRequest


@pytest.mark.parametrize("schema", [MealInput, MealRequest])
@pytest.mark.parametrize("source", ["usda", "manual_estimate", "meal_plan"])
def test_meal_log_requires_exactly_one_food(schema, source):
    item = {
        "food_name": "Rice",
        "quantity": 1,
        "unit": "serving",
        "calories": 200,
        "protein_g": 4,
        "carbohydrate_g": 40,
        "fat_g": 2,
        "source": source,
    }
    payload = {
        "eaten_at": "2026-10-01T08:00:00Z",
        "meal_type": "lunch",
        "items": [item],
    }
    if schema is MealRequest:
        payload["user_id"] = 1
    assert len(schema.model_validate(payload).items) == 1
    for items in ([], [item, item]):
        with pytest.raises(ValidationError):
            schema.model_validate({**payload, "items": items})
