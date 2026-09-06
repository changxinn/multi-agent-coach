"""Restriction and allergy safety coverage for static meal templates."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.nutrition_agent.app import main as nutrition_main
from services.nutrition_agent.app.assessment import REFERRAL
from services.nutrition_agent.app.schemas import MealPlanRequest
from services.nutrition_agent.app.tools.meal_planner import generate_meal_plan, select_meal

MACROS = {"calories": 1_800, "protein_g": 100, "carbs_g": 200, "fat_g": 60}


def test_select_meal_applies_minimum_and_maximum_fat_constraints() -> None:
    meal = select_meal("dinner", min_fat_g=20, max_fat_g=25)

    assert meal is not None
    assert 20 <= meal["fat_g"] <= 25
    assert select_meal("dinner", min_fat_g=100) is None


def test_planner_filters_allergy_and_restriction_tags_before_selecting_templates() -> None:
    plan = generate_meal_plan(
        MACROS,
        "omnivore",
        3,
        allergies=["dAiRy"],
        dietary_restrictions=["fish"],
    )

    assert plan is not None
    names = [meal["name"].casefold() for meal in plan["meals"].values()]
    assert all("yogurt" not in name for name in names)
    assert all("tuna" not in name and "salmon" not in name for name in names)


def test_planner_returns_no_plan_when_required_meal_category_has_no_safe_template() -> None:
    assert generate_meal_plan(
        MACROS,
        "omnivore",
        3,
        allergies=["eggs", "oats", "dairy"],
    ) is None


@pytest.mark.asyncio
async def test_meal_plan_passes_profile_and_request_constraints_to_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def profile(_: int) -> SimpleNamespace:
        return SimpleNamespace(
            allergies=["dairy"],
            dietary_restrictions=["fish"],
            dietary_preference="omnivore",
            meals_per_day=3,
        )

    def planner(*_: object, **kwargs: object) -> dict:
        captured.update(kwargs)
        return {
            "meals": {"breakfast": {"name": "Safe breakfast", **MACROS}},
            "total_calories": 400,
            "total_protein_g": 20,
            "total_carbs_g": 40,
            "total_fat_g": 10,
        }

    monkeypatch.setattr(nutrition_main.repository, "get_profile", profile)
    monkeypatch.setattr(nutrition_main, "generate_meal_plan", planner)

    await nutrition_main.meal_plan(
        42,
        MealPlanRequest(target_inputs={
            "age": 30, "gender": "female", "weight_kg": 65, "height_cm": 165,
            "activity_level": "moderate", "fitness_goal": "maintenance",
        }, days=1, excluded_foods=["peanuts"]),
    )

    assert captured["allergies"] == ["dairy", "peanuts"]
    assert captured["dietary_restrictions"] == ["fish"]


@pytest.mark.asyncio
async def test_meal_plan_refuses_unsatisfiable_constraints_without_exposing_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive_constraints = ["eggs", "oats", "dairy"]

    async def profile(_: int) -> SimpleNamespace:
        return SimpleNamespace(
            allergies=sensitive_constraints,
            dietary_restrictions=[],
            dietary_preference="omnivore",
            meals_per_day=3,
        )

    monkeypatch.setattr(nutrition_main.repository, "get_profile", profile)

    with pytest.raises(HTTPException) as raised:
        await nutrition_main.meal_plan(
            42,
            MealPlanRequest(target_inputs={
                "age": 30, "gender": "female", "weight_kg": 65, "height_cm": 165,
                "activity_level": "moderate", "fitness_goal": "maintenance",
            }, days=1),
        )

    assert raised.value.status_code == 422
    assert raised.value.detail == {
        "code": "NUTRITION_SAFETY_REFERRAL_REQUIRED",
        "message": REFERRAL,
    }
    assert all(value not in str(raised.value.detail).casefold() for value in sensitive_constraints)