"""Eligibility rules shared by every meal-plan generation path."""

from decimal import Decimal, InvalidOperation
from typing import Any

from .food_compatibility_policy import compatibility_failure_reason


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


def is_compatible_for_meal_plan(
    food: dict[str, Any],
    metadata: dict[str, Any] | None,
    profile: dict[str, Any] | None,
) -> bool:
    """Return whether food is eligible and has approved compatible metadata."""
    return (
        is_eligible_for_meal_plan(food)
        and compatibility_failure_reason(metadata, profile) is None
    )
