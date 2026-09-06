"""Regression coverage for daily assessment-history adherence wiring."""

from __future__ import annotations

import pytest

from services.nutrition_agent.app.assessment import NutritionHistory, assess_nutrition
from services.nutrition_agent.app.repository import (
    NutritionRepository,
    nutrition_history_from_daily_rows,
)
from services.nutrition_agent.app.schemas import NutritionEvaluateRequest


def _day(
    *,
    meal_logs: int = 1,
    calories: float | None = 2_000,
    protein_g: float | None = 100,
    carbs_g: float | None = 200,
    fat_g: float | None = 60,
    target_calories: float | None = 2_000,
    targets: dict[str, float] | None = None,
) -> dict[str, object]:
    return {
        "meal_logs": meal_logs,
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "target_calories": target_calories,
        "target_macro_targets": (
            targets if targets is not None
            else {"protein_g": 100, "carbs_g": 200, "fat_g": 60}
        ),
    }


def test_daily_projection_aggregates_logs_and_uses_effective_target_values() -> None:
    history = nutrition_history_from_daily_rows([
        _day(meal_logs=3, calories=2_000),
        _day(meal_logs=2, calories=1_000),
        _day(meal_logs=1, calories=4_000),
    ])

    assert history.meal_logs_last_7_days == 6
    assert history.average_calories == pytest.approx(2333.333333)
    assert history.adherence_percentage == 66.7
    assert history.macro_adherence_percentages == {
        "protein_g": 100.0, "carbs_g": 100.0, "fat_g": 100.0,
    }


@pytest.mark.parametrize(
    "rows",
    [
        [_day(target_calories=None, targets={}) for _ in range(3)],
        [_day(target_calories=0) for _ in range(3)],
        [_day() for _ in range(2)],
    ],
)
def test_adherence_is_null_without_valid_target_or_sufficient_comparable_days(rows: list[dict[str, object]]) -> None:
    history = nutrition_history_from_daily_rows(rows)

    assert history.adherence_percentage is None
    assert history.macro_adherence_percentages is None


def test_macro_adherence_is_null_per_nutrient_without_three_comparable_days() -> None:
    history = nutrition_history_from_daily_rows([
        _day(protein_g=None), _day(protein_g=None), _day(),
    ])

    assert history.macro_adherence_percentages == {
        "protein_g": None, "carbs_g": 100.0, "fat_g": 100.0,
    }


def test_assessment_uses_low_macro_adherence_but_safety_escalation_remains_terminal() -> None:
    history = NutritionHistory(
        meal_logs_last_7_days=7,
        macro_adherence_percentages={"protein_g": 60.0, "carbs_g": 100.0, "fat_g": 100.0},
    )

    safe = assess_nutrition(NutritionEvaluateRequest(message="Please assess my meals"), history, {})
    escalated = assess_nutrition(NutritionEvaluateRequest(message="I use insulin"), history, {})

    assert safe.score == 1
    assert "macronutrient targets" in safe.recommendations[0]
    assert escalated.status == "escalate"
    assert escalated.score == 10


def test_assessment_returns_high_protein_breakfast_within_requested_calorie_ceiling() -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(
            message="I train four days each week. Give me a high-protein breakfast under 500 calories."
        ),
        NutritionHistory(),
        {"dietary_preference": "omnivore", "allergies": [], "dietary_restrictions": []},
    )

    assert "Greek yogurt protein bowl with berries" in assessment.message
    assert "430 calories" in assessment.message
    assert "40 g protein" in assessment.message


def test_assessment_returns_highest_protein_dinner_without_calorie_ceiling() -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Next, give me a high-protein dinner."),
        NutritionHistory(),
        {"dietary_preference": "omnivore", "allergies": [], "dietary_restrictions": []},
    )

    assert "Lean beef with sweet potato" in assessment.message
    assert "520 calories" in assessment.message
    assert "42 g protein" in assessment.message


def test_assessment_returns_fiber_aware_balanced_dinner_instead_of_highest_protein_dinner() -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Give me a balanced dinner with carbs, protein, and fiber."),
        NutritionHistory(),
        {"dietary_preference": "omnivore", "allergies": [], "dietary_restrictions": []},
    )

    assert "Salmon with brown rice and broccoli" in assessment.message
    assert "550 calories" in assessment.message
    assert "40 g protein" in assessment.message
    assert "45 g carbohydrates" in assessment.message
    assert "8 g fiber" in assessment.message
    assert "22 g fat" in assessment.message
    assert assessment.meal_recommendations[0].fat_g == 22
    assert assessment.meal_recommendations[0].satisfies == ["protein", "carbohydrates", "fiber", "fat"]
    assert "Lean beef with sweet potato" not in assessment.message


def test_assessment_applies_numeric_fat_bounds_to_structured_meal_options() -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Give me a dinner with at least 20 g fat and under 25 g fat."),
        NutritionHistory(),
        {"dietary_preference": "omnivore", "allergies": [], "dietary_restrictions": []},
    )

    assert assessment.meal_recommendations[0].name == "Salmon with brown rice and broccoli"
    assert 20 <= assessment.meal_recommendations[0].fat_g <= 25
    assert assessment.meal_recommendations[0].satisfies == ["fat"]
    assert "22 g fat" in assessment.message


def test_assessment_reports_unsatisfiable_numeric_fat_constraint_without_meal_option() -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Give me a dinner with at least 100 g fat."),
        NutritionHistory(),
        {"dietary_preference": "omnivore", "allergies": [], "dietary_restrictions": []},
    )

    assert assessment.meal_recommendations == []
    assert "couldn’t find a dinner template" in assessment.message


def test_assessment_returns_balanced_main_meal_options_when_timing_is_unspecified() -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Give me a balanced meal with fiber, carbs, and protein."),
        NutritionHistory(),
        {"dietary_preference": "omnivore", "allergies": [], "dietary_restrictions": []},
    )

    assert len(assessment.recommendations) == 3
    assert "Greek yogurt protein bowl with berries" in assessment.message
    assert "Grilled chicken salad with quinoa" in assessment.message
    assert "Salmon with brown rice and broccoli" in assessment.message
    assert all("calories" in recommendation for recommendation in assessment.recommendations)
    assert all("g protein" in recommendation for recommendation in assessment.recommendations)
    assert all("g carbohydrates" in recommendation for recommendation in assessment.recommendations)
    assert all("8 g fiber" in recommendation for recommendation in assessment.recommendations)
    assert "Log meals consistently" not in assessment.message


def test_assessment_returns_high_protein_main_meal_options_when_timing_is_unspecified() -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Give me a high-protein meal."),
        NutritionHistory(),
        {"dietary_preference": "omnivore", "allergies": [], "dietary_restrictions": []},
    )

    assert len(assessment.recommendations) == 3
    assert "Greek yogurt protein bowl with berries" in assessment.message
    assert "Grilled chicken salad with quinoa" in assessment.message
    assert "Lean beef with sweet potato" in assessment.message
    assert "Log meals consistently" not in assessment.message


def test_assessment_keeps_explicit_snack_request_snack_only() -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Give me a high-protein snack."),
        NutritionHistory(),
        {"dietary_preference": "omnivore", "allergies": [], "dietary_restrictions": []},
    )

    assert len(assessment.recommendations) == 1
    assert "couldn’t find a snack template" in assessment.message
    assert "Greek yogurt protein bowl with berries" not in assessment.message
    assert "Lean beef with sweet potato" not in assessment.message


@pytest.mark.parametrize(
    ("dietary_preference", "expected_name", "expected_calories", "expected_protein", "expected_carbs", "expected_fiber"),
    [
        ("vegetarian", "Vegetable curry with chickpeas", 450, 18, 60, 14),
        ("vegan", "Black bean tacos with avocado", 460, 18, 55, 15),
    ],
)
def test_assessment_returns_dietary_appropriate_balanced_fiber_aware_dinner(
    dietary_preference: str,
    expected_name: str,
    expected_calories: int,
    expected_protein: int,
    expected_carbs: int,
    expected_fiber: int,
) -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Give me a balanced dinner with carbs, protein, and fiber."),
        NutritionHistory(),
        {"dietary_preference": dietary_preference, "allergies": [], "dietary_restrictions": []},
    )

    assert expected_name in assessment.message
    assert f"{expected_calories} calories" in assessment.message
    assert f"{expected_protein} g protein" in assessment.message
    assert f"{expected_carbs} g carbohydrates" in assessment.message
    assert f"{expected_fiber} g fiber" in assessment.message


def test_assessment_dinner_suggestion_respects_calorie_ceiling() -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Give me a high-protein dinner under 500 calories."),
        NutritionHistory(),
        {"dietary_preference": "omnivore", "allergies": [], "dietary_restrictions": []},
    )

    assert "Chicken stir-fry with vegetables" in assessment.message
    assert "480 calories" in assessment.message
    assert "38 g protein" in assessment.message


def test_assessment_dinner_suggestion_respects_profile_exclusions() -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Give me a high-protein dinner."),
        NutritionHistory(),
        {
            "dietary_preference": "omnivore",
            "allergies": ["fish", "chicken"],
            "dietary_restrictions": [],
        },
    )

    assert "Lean beef with sweet potato" in assessment.message


def test_assessment_breakfast_suggestion_respects_profile_exclusions() -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Give me a high-protein breakfast under 500 calories."),
        NutritionHistory(),
        {
            "dietary_preference": "omnivore",
            "allergies": ["dairy", "eggs"],
            "dietary_restrictions": [],
        },
    )

    assert "couldn’t find a breakfast template" in assessment.message


@pytest.mark.parametrize(
    ("dietary_preference", "expected_name", "expected_calories", "expected_protein"),
    [
        ("vegetarian", "Cottage cheese protein bowl with berries", 390, 36),
        ("vegan", "Tofu and soy yogurt protein bowl", 440, 32),
    ],
)
def test_assessment_returns_dietary_appropriate_high_protein_breakfast(
    dietary_preference: str,
    expected_name: str,
    expected_calories: int,
    expected_protein: int,
) -> None:
    assessment = assess_nutrition(
        NutritionEvaluateRequest(message="Give me a high-protein breakfast under 500 calories."),
        NutritionHistory(),
        {"dietary_preference": dietary_preference, "allergies": [], "dietary_restrictions": []},
    )

    assert expected_name in assessment.message
    assert f"{expected_calories} calories" in assessment.message
    assert f"{expected_protein} g protein" in assessment.message


@pytest.mark.asyncio
async def test_repository_history_uses_daily_utc_grouping_and_target_revisions() -> None:
    class Settings:
        @staticmethod
        def validated_schema() -> str:
            return "systemdb"

    class Pool:
        query = ""

        async def fetch(self, query: str, *_: object) -> list[dict[str, object]]:
            self.query = query
            return [_day(), _day(), _day()]

    repository = NutritionRepository(Settings())
    pool = Pool()
    repository.pool = pool  # type: ignore[assignment]

    history = await repository.history(42)

    assert history.adherence_percentage == 100.0
    assert "logged_at AT TIME ZONE 'UTC'" in pool.query
    assert "GROUP BY (logged_at AT TIME ZONE 'UTC')::date" in pool.query
    assert "ORDER BY effective_from DESC, version DESC" in pool.query