"""Private Nutrition safety enforcement and presentation wiring."""

from __future__ import annotations

import json
from math import isfinite

import pytest
from fastapi import HTTPException

from services.nutrition_agent.app import main as nutrition_main
from services.nutrition_agent.app.assessment import (
    DISCLAIMER,
    REFERRAL,
    NutritionHistory,
)
from services.nutrition_agent.app.repository import NutritionRepository
from services.nutrition_agent.app.schemas import (
    MealPlanRequest,
    NutritionEvaluateRequest,
    SafetyContext,
    TargetCalculateRequest,
    TargetInputs,
    TargetSaveRequest,
)
from services.nutrition_agent.app.tools.macro_targets import calculate_macro_targets


def target_inputs(**updates: object) -> TargetInputs:
    values: dict[str, object] = {
        "age": 30,
        "gender": "female",
        "weight_kg": 65,
        "height_cm": 165,
        "activity_level": "moderate",
        "fitness_goal": "maintenance",
    }
    values.update(updates)
    return TargetInputs(**values)


@pytest.mark.parametrize("gender", ["female", "male", "other"])
@pytest.mark.parametrize("fitness_goal", ["weight_loss", "maintenance", "muscle_gain"])
def test_macro_targets_are_non_negative_and_percentages_are_valid_for_all_genders(
    gender: str, fitness_goal: str,
) -> None:
    targets = calculate_macro_targets(2_400, 75, fitness_goal, gender)

    assert all(targets[key] >= 0 for key in ("protein_g", "carbs_g", "fat_g"))
    percentages = [targets[key] for key in (
        "protein_percentage", "carbs_percentage", "fat_percentage",
    )]
    assert all(isfinite(percentage) and 0 <= percentage <= 100 for percentage in percentages)
    assert sum(percentages) == pytest.approx(100, abs=0.1)


@pytest.mark.parametrize("gender, minimum_calories", [("female", 1_200), ("male", 1_500), ("other", 1_200)])
def test_macro_targets_normalize_high_weight_calorie_floor_without_negative_carbs(
    gender: str, minimum_calories: int,
) -> None:
    targets = calculate_macro_targets(1_000, 300, "weight_loss", gender)

    assert targets["calories"] == minimum_calories
    assert targets["carbs_g"] == 0
    assert all(targets[key] >= 0 for key in ("protein_g", "fat_g"))
    assert sum(targets[key] for key in (
        "protein_percentage", "carbs_percentage", "fat_percentage",
    )) == pytest.approx(100, abs=0.1)


ESCALATING_CONTEXTS = [
    SafetyContext(risk_flags=["chest_pain_or_breathing_difficulty"]),
    SafetyContext(risk_flags=["fainting_or_severe_dizziness"]),
    SafetyContext(risk_flags=["purging_or_laxative_use"]),
    SafetyContext(risk_flags=["severe_food_restriction"]),
    SafetyContext(risk_flags=["current_disordered_eating_behaviors"]),
    SafetyContext(medical_conditions=["eating_disorder_history"]),
    SafetyContext(pregnancy_lactation_status="pregnant"),
    SafetyContext(medical_conditions=["diabetes"]),
    SafetyContext(medical_conditions=["kidney_disease"]),
    SafetyContext(medical_conditions=["hypertension"]),
    SafetyContext(risk_flags=["under_18"]),
    SafetyContext(risk_flags=["rapid_weight_loss_request"]),
    SafetyContext(risk_flags=["other_medical_condition"]),
]


def test_target_calculation_returns_structured_referral_for_context_risk() -> None:
    payload = TargetCalculateRequest(
        inputs=target_inputs(safety_context=SafetyContext(risk_flags=["under_18"]))
    )

    with pytest.raises(HTTPException) as raised:
        nutrition_main.target_calculation(payload)

    assert raised.value.status_code == 422
    assert raised.value.detail["code"] == "NUTRITION_SAFETY_REFERRAL_REQUIRED"


@pytest.mark.parametrize("context", ESCALATING_CONTEXTS)
def test_every_escalation_code_blocks_target_calculation(context: SafetyContext) -> None:
    with pytest.raises(HTTPException) as raised:
        nutrition_main.target_calculation(TargetCalculateRequest(inputs=target_inputs(safety_context=context)))

    assert raised.value.status_code == 422
    assert raised.value.detail["code"] == "NUTRITION_SAFETY_REFERRAL_REQUIRED"


@pytest.mark.asyncio
@pytest.mark.parametrize("context", ESCALATING_CONTEXTS)
async def test_every_escalation_code_blocks_target_save_before_persistence(
    monkeypatch: pytest.MonkeyPatch, context: SafetyContext
) -> None:
    async def unexpected(*_: object) -> None:
        raise AssertionError("unsafe target must not be saved")

    monkeypatch.setattr(nutrition_main.repository, "save_target", unexpected)
    with pytest.raises(HTTPException) as raised:
        await nutrition_main.save_target(
            42,
            TargetSaveRequest(inputs=target_inputs(safety_context=context), effective_from="2026-09-01"),
        )

    assert raised.value.status_code == 422
    assert raised.value.detail["code"] == "NUTRITION_SAFETY_REFERRAL_REQUIRED"


def test_target_calculation_rechecks_calorie_dependent_safety(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        nutrition_main,
        "calculate_macro_targets",
        lambda *_: {"calories": 1_100, "protein_g": 80, "carbs_g": 120, "fat_g": 35},
    )

    result = nutrition_main.target_calculation(TargetCalculateRequest(inputs=target_inputs()))

    assert result["safety_findings"] == [
        {"code": "BELOW_MINIMUM_CALORIE_FLOOR", "severity": "warning"}
    ]


@pytest.mark.asyncio
async def test_meal_plan_blocks_context_risk_before_repository_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected(*_: object) -> None:
        raise AssertionError("repository must not be accessed after a safety referral")

    monkeypatch.setattr(nutrition_main.repository, "get_profile", unexpected)
    payload = MealPlanRequest(
        use_current_target=True,
        days=1,
        safety_context=SafetyContext(medical_conditions=["diabetes"]),
    )

    with pytest.raises(HTTPException) as raised:
        await nutrition_main.meal_plan(42, payload)

    assert raised.value.detail["code"] == "NUTRITION_SAFETY_REFERRAL_REQUIRED"


@pytest.mark.asyncio
@pytest.mark.parametrize("context", ESCALATING_CONTEXTS)
async def test_every_escalation_code_blocks_meal_plan_before_repository_access(
    monkeypatch: pytest.MonkeyPatch, context: SafetyContext
) -> None:
    async def unexpected(*_: object) -> None:
        raise AssertionError("unsafe meal plan must not access the repository")

    monkeypatch.setattr(nutrition_main.repository, "get_profile", unexpected)
    with pytest.raises(HTTPException) as raised:
        await nutrition_main.meal_plan(42, MealPlanRequest(use_current_target=True, days=1, safety_context=context))

    assert raised.value.status_code == 422
    assert raised.value.detail["code"] == "NUTRITION_SAFETY_REFERRAL_REQUIRED"


@pytest.mark.asyncio
async def test_evaluate_presents_before_persisting(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def history(_: int) -> NutritionHistory:
        return NutritionHistory()

    async def save(_: int, assessment: object) -> None:
        captured["assessment"] = assessment

    def present(assessment: object, message: str) -> object:
        captured["message"] = message
        return assessment.model_copy(update={"message": "Presented response."})

    monkeypatch.setattr(nutrition_main.repository, "history", history)
    monkeypatch.setattr(nutrition_main.repository, "save_assessment", save)
    monkeypatch.setattr(nutrition_main.agent, "present", present)

    result = await nutrition_main.evaluate(42, NutritionEvaluateRequest(message="Need nutrition help"))

    assert captured["message"] == "Need nutrition help"
    assert captured["assessment"] is result
    assert result.message == "Presented response."


@pytest.mark.asyncio
async def test_evaluate_attaches_persisted_target_to_meal_recommendation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def history(_: int) -> NutritionHistory:
        return NutritionHistory()

    async def current_target(_: int, __: object) -> dict[str, object]:
        return {
            "inputs": {"age": 30, "gender": "female", "weight_kg": 65,
                       "height_cm": 165, "activity_level": "moderate"},
            "recommended_calories": 2_000,
            "macro_targets": {"protein_g": 130, "carbs_g": 250, "fat_g": 60},
        }

    async def save(*_: object) -> None:
        return None

    monkeypatch.setattr(nutrition_main.repository, "history", history)
    monkeypatch.setattr(nutrition_main.repository, "current_target", current_target)
    monkeypatch.setattr(nutrition_main.repository, "save_assessment", save)
    monkeypatch.setattr(nutrition_main.agent, "present", lambda assessment, _: assessment)

    result = await nutrition_main.evaluate(
        42, NutritionEvaluateRequest(message="Give me a high-protein lunch.")
    )

    assert result.target_available is True
    assert result.tdee is not None
    assert result.macro_targets == {"protein_g": 130, "carbs_g": 250, "fat_g": 60}
    assert result.meal_recommendations[0].target_percentages is not None
    assert result.meal_recommendations[0].target_percentages["protein_g"] > 0


@pytest.mark.asyncio
async def test_evaluate_meal_without_persisted_target_stays_target_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def history(_: int) -> NutritionHistory:
        return NutritionHistory()

    async def current_target(_: int, __: object) -> None:
        return None

    async def save(*_: object) -> None:
        return None

    monkeypatch.setattr(nutrition_main.repository, "history", history)
    monkeypatch.setattr(nutrition_main.repository, "current_target", current_target)
    monkeypatch.setattr(nutrition_main.repository, "save_assessment", save)
    monkeypatch.setattr(nutrition_main.agent, "present", lambda assessment, _: assessment)

    result = await nutrition_main.evaluate(
        42, NutritionEvaluateRequest(message="Give me a high-protein lunch.")
    )

    assert result.target_available is False
    assert result.tdee is None
    assert result.macro_targets is None
    assert result.meal_recommendations[0].target_percentages is None


@pytest.mark.asyncio
async def test_evaluate_incomplete_persisted_target_stays_target_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def history(_: int) -> NutritionHistory:
        return NutritionHistory()

    async def current_target(_: int, __: object) -> dict[str, object]:
        return {"inputs": "not-json", "recommended_calories": 2_000, "macro_targets": {}}

    async def save(*_: object) -> None:
        return None

    monkeypatch.setattr(nutrition_main.repository, "history", history)
    monkeypatch.setattr(nutrition_main.repository, "current_target", current_target)
    monkeypatch.setattr(nutrition_main.repository, "save_assessment", save)
    monkeypatch.setattr(nutrition_main.agent, "present", lambda assessment, _: assessment)

    result = await nutrition_main.evaluate(
        42, NutritionEvaluateRequest(message="Give me a high-protein lunch.")
    )

    assert result.target_available is False
    assert result.tdee is None


@pytest.mark.asyncio
async def test_evaluate_escalation_bypasses_presentation_and_persists_terminal_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def history(_: int) -> NutritionHistory:
        return NutritionHistory()

    async def save(_: int, assessment: object) -> None:
        captured["assessment"] = assessment

    def presentation_must_not_run(*_: object) -> object:
        raise AssertionError("presentation must not run for a terminal escalation")

    monkeypatch.setattr(nutrition_main.repository, "history", history)
    monkeypatch.setattr(nutrition_main.repository, "save_assessment", save)
    monkeypatch.setattr(nutrition_main.agent, "present", presentation_must_not_run)

    result = await nutrition_main.evaluate(
        42,
        NutritionEvaluateRequest(message="I need a supplement dosage while taking insulin."),
    )

    assert captured["assessment"] is result
    assert result.status == "escalate"
    assert result.score == 10
    assert [finding.code for finding in result.safety_findings] == [
        "DIABETES_OR_INSULIN",
        "OTHER_MEDICAL_CONDITION",
    ]
    assert result.escalation is not None
    assert result.escalation.urgent is False
    assert REFERRAL in result.message
    assert DISCLAIMER in result.message
    assert result.recommendations == ["Seek qualified healthcare support."]
    assert result.tdee is None
    assert result.macro_targets is None


@pytest.mark.asyncio
async def test_escalation_response_and_persistence_projection_exclude_raw_safety_data() -> None:
    class Settings:
        @staticmethod
        def validated_schema() -> str:
            return "systemdb"

    class Pool:
        arguments: tuple[object, ...]

        async def execute(self, _: str, *arguments: object) -> None:
            self.arguments = arguments

    raw_phrase = "I need supplement advice while taking an unlisted medication"
    context = SafetyContext(medical_conditions=["diabetes"], risk_flags=["other_medical_condition"])
    assessment = nutrition_main.assess_nutrition(
        NutritionEvaluateRequest(message=raw_phrase, safety_context=context), NutritionHistory(), {}
    )
    repository = NutritionRepository(Settings())
    pool = Pool()
    repository.pool = pool  # type: ignore[assignment]
    await repository.save_assessment(42, assessment)

    response = assessment.model_dump(mode="json")
    stored = " ".join(argument if isinstance(argument, str) else json.dumps(argument) for argument in pool.arguments)
    assert assessment.status == "escalate"
    assert assessment.tdee is None and assessment.macro_targets is None
    assert "meal plan" in assessment.escalation.message.lower()
    for secret in (raw_phrase, "unlisted medication", "medical_conditions", "risk_flags", "diabetes"):
        assert secret not in json.dumps(response)
        assert secret not in stored