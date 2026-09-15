"""LLM-first Nutrition meal recommendation safety and context coverage."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.nutrition_agent.app import main as nutrition_main
from services.nutrition_agent.app.assessment import NutritionHistory
from services.nutrition_agent.app.schemas import (
    MealRecommendation,
    NutritionEvaluateRequest,
)


def _profile(*, allergies: list[str] | None = None) -> dict[str, object]:
    return {
        "timezone": "UTC",
        "dietary_preference": "omnivore",
        "allergies": allergies or [],
        "dietary_restrictions": [],
    }


async def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        nutrition_main.repository, "history", AsyncMock(return_value=NutritionHistory())
    )
    monkeypatch.setattr(nutrition_main.repository, "save_assessment", AsyncMock())
    monkeypatch.setattr(
        nutrition_main.repository, "current_target", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        nutrition_main.agent, "present", lambda assessment, _: assessment
    )


def _supper() -> SimpleNamespace:
    return SimpleNamespace(
        clarification=None,
        recommendations=[
            MealRecommendation(
                meal_type="supper",
                name="Turkey, lentil, and rice bowl",
                description="Turkey, lentils, rice, roasted vegetables, and tahini.",
                rationale="Higher energy and protein support the stated bulking focus.",
                calories=760,
                protein_g=52,
                carbs_g=92,
                fiber_g=14,
                fat_g=20,
                satisfies=["protein", "carbohydrates"],
            )
        ],
    )


@pytest.mark.asyncio
async def test_llm_first_supper_recommendation_uses_chronological_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _setup(monkeypatch)
    captured: dict[str, object] = {}

    def recommend(**kwargs: object) -> object:
        captured.update(kwargs)
        assert "catalog" not in kwargs
        return _supper()

    monkeypatch.setattr(nutrition_main.agent, "recommend_meals", recommend)
    context = {
        "version": "chat-history-v1",
        "summary": None,
        "messages": [
            {"role": "user", "content": "Give me a dinner option."},
            {"role": "assistant", "content": "Here is a dinner option."},
            {"role": "user", "content": "Make it high-protein for bulking."},
            {"role": "assistant", "content": "I can prioritize protein and energy."},
            {"role": "user", "content": "I mean supper, not dinner."},
        ],
    }
    result = await nutrition_main.evaluate(
        42,
        NutritionEvaluateRequest(
            message="Give me a supper option.", profile=_profile(), chat_context=context
        ),
    )
    assert captured["chat_context"] == {
        **context,
        "recent_meal_recommendations": [],
    }
    assert result.meal_recommendations[0].meal_type == "supper"
    assert "(supper)" in result.message
    assert "bulking" in result.message.casefold()


@pytest.mark.asyncio
async def test_internal_language_and_restricted_foods_never_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _setup(monkeypatch)
    unsafe = SimpleNamespace(
        clarification=None,
        recommendations=[
            MealRecommendation(
                meal_type="supper",
                name="Eligible catalog JSON peanut bowl",
                calories=700,
                protein_g=40,
                carbs_g=80,
                fiber_g=10,
                fat_g=20,
            )
        ],
    )
    monkeypatch.setattr(nutrition_main.agent, "recommend_meals", lambda **_: unsafe)
    result = await nutrition_main.evaluate(
        42,
        NutritionEvaluateRequest(
            message="A supper option", profile=_profile(allergies=["peanut"])
        ),
    )
    assert result.meal_recommendations == []
    assert "unable to generate" in result.message.casefold()
    assert all(
        term not in result.message.casefold()
        for term in ("eligible catalog", "json", "peanut")
    )


@pytest.mark.asyncio
async def test_model_unavailable_does_not_substitute_a_catalog_meal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _setup(monkeypatch)
    monkeypatch.setattr(nutrition_main.agent, "recommend_meals", lambda **_: None)
    result = await nutrition_main.evaluate(
        42,
        NutritionEvaluateRequest(
            message="Give me a high-protein supper.", profile=_profile()
        ),
    )
    assert result.meal_recommendations == []
    assert "unable to generate" in result.message.casefold()


@pytest.mark.asyncio
async def test_safety_escalation_never_calls_meal_recommendation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _setup(monkeypatch)
    monkeypatch.setattr(
        nutrition_main.agent, "recommend_meals", lambda **_: pytest.fail("must not run")
    )
    result = await nutrition_main.evaluate(
        42,
        NutritionEvaluateRequest(
            message="I need a supper while taking insulin.", profile=_profile()
        ),
    )
    assert result.status == "escalate"
