"""Eligibility rules shared by every meal-plan generation path."""

from decimal import Decimal, InvalidOperation
from typing import Any


def contains_alcohol(food: dict[str, Any]) -> bool:
    """Return whether USDA reports a positive ethyl alcohol nutrient amount."""
    raw_response = food.get("raw_response")
    if not isinstance(raw_response, dict):
        return False
    nutrients = raw_response.get("foodNutrients")
    if not isinstance(nutrients, list):
        return False
    for nutrient in nutrients:
        if not isinstance(nutrient, dict) or nutrient.get("name") != "Alcohol, ethyl":
            continue
        try:
            return Decimal(str(nutrient.get("amount"))) > 0
        except (InvalidOperation, TypeError, ValueError):
            return False
    return False


def is_eligible_for_meal_plan(food: dict[str, Any]) -> bool:
    """Exclude foods explicitly identified by USDA as containing alcohol."""
    return not contains_alcohol(food)
