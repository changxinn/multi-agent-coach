"""Deterministic safety assessment for persisted meal-plan content."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


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
    allergies = _normalise_values(profile, "allergies")
    assessed_meals: list[dict[str, Any]] = []
    plan_warnings: list[str] = []

    if profile is None:
        plan_warnings.append(
            "Nutrition profile is missing; food safety requires review."
        )
    for meal in planned_meals:
        assessment = _assess_meal(meal, profile is not None, allergies, foods_by_id)
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
    has_profile: bool,
    allergies: set[str],
    foods_by_id: dict[int, dict[str, Any]],
) -> MealSafetyAssessment:
    warnings: list[str] = []
    blocked: list[str] = []
    if not has_profile:
        warnings.append("Nutrition profile is missing; meal safety requires review.")
    for item in meal["items"]:
        food_id = item.get("food_cache_id")
        food = foods_by_id.get(food_id) if food_id else None
        name = item["food_name"]
        if food is None:
            warnings.append(f"{name}: no cached allergen metadata; review required.")
            continue
        if food.get("allergen_status") != "known":
            warnings.append(f"{name}: allergen metadata is unknown; review required.")
            continue
        matches = allergies & _normalise_allergen_data(food.get("allergen_data"))
        if matches:
            blocked.append(
                f"{name}: conflicts with confirmed allergy {', '.join(sorted(matches))}."
            )

    if blocked:
        return MealSafetyAssessment("blocked", blocked + warnings)
    if warnings:
        return MealSafetyAssessment("review_required", warnings)
    return MealSafetyAssessment("safe", [])


def _normalise_values(profile: dict[str, Any] | None, field: str) -> set[str]:
    if not profile:
        return set()
    values = profile.get(field) or []
    return {_normalise(value) for value in values if _normalise(value)}


def _normalise_allergen_data(value: Any) -> set[str]:
    return {
        normalised
        for text in _strings(value)
        for normalised in (_normalise(text),)
        if normalised
    }


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _strings(nested)


def _normalise(value: Any) -> str:
    return " ".join(str(value).casefold().replace("_", " ").split())
