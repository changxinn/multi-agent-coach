"""Deterministic safety assessment for persisted meal-plan content."""

from dataclasses import dataclass
from typing import Any

from .food_compatibility_policy import compatibility_failure_reason
from .meal_plan_eligibility import is_eligible_for_meal_plan


@dataclass(frozen=True)
class MealSafetyAssessment:
    status: str
    warnings: list[str]


def assess_meal_plan_safety(
    planned_meals: list[dict[str, Any]],
    profile: dict[str, Any] | None,
    foods_by_id: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Assign server-owned safety statuses without treating missing data as safe."""
    assessed_meals: list[dict[str, Any]] = []
    plan_warnings: list[str] = []

    if profile is None:
        plan_warnings.append(
            "Nutrition profile is missing; food safety requires review."
        )
    for meal in planned_meals:
        assessment = _assess_meal(meal, profile, foods_by_id)
        assessed_meals.append(
            {
                **meal,
                "safety_status": assessment.status,
                "safety_warnings": assessment.warnings,
            }
        )
        plan_warnings.extend(assessment.warnings)

    return assessed_meals, list(dict.fromkeys(plan_warnings))


def _assess_meal(
    meal: dict[str, Any],
    profile: dict[str, Any] | None,
    foods_by_id: dict[int, dict[str, Any]],
) -> MealSafetyAssessment:
    warnings: list[str] = []
    blocked: list[str] = []
    if profile is None:
        warnings.append("Nutrition profile is missing; meal safety requires review.")
    for item in meal["items"]:
        food_id = item.get("food_cache_id")
        food = foods_by_id.get(food_id) if food_id else None
        name = item["food_name"]
        if food is None:
            warnings.append(f"{name}: no cached allergen metadata; review required.")
            continue
        reason = compatibility_failure_reason(food, profile)
        if reason:
            blocked.append(f"{name}: {reason}.")
        elif not is_eligible_for_meal_plan(food):
            blocked.append(f"{name}: contains alcohol according to USDA nutrient data.")

    if blocked:
        return MealSafetyAssessment("blocked", blocked + warnings)
    if warnings:
        return MealSafetyAssessment("review_required", warnings)
    return MealSafetyAssessment("safe", [])
