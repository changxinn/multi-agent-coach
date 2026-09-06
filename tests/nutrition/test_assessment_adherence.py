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