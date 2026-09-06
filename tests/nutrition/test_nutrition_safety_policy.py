"""Focused deterministic message-signal regression coverage."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.nutrition_agent.app.assessment import escalation_for, safety_findings
from services.nutrition_agent.app.schemas import SafetyContext, TargetInputs


@pytest.mark.parametrize(
    ("message", "expected_code", "urgent"),
    [
        ("I have CHEST PAIN after a run.", "CHEST_PAIN_OR_BREATHING_DIFFICULTY", True),
        ("I passed out during training.", "FAINTING_OR_SEVERE_DIZZINESS", True),
        ("I am pregnant; can you make a meal plan?", "PREGNANCY_OR_BREASTFEEDING", False),
        ("My insulin changed. What should I eat?", "DIABETES_OR_INSULIN", False),
        ("I have renal disease and want to fast.", "KIDNEY_DISEASE", False),
        ("What supplement dosage should I take?", "OTHER_MEDICAL_CONDITION", False),
    ],
)
def test_high_risk_message_signals_escalate(
    message: str,
    expected_code: str,
    urgent: bool,
) -> None:
    findings = safety_findings(message)
    escalation = escalation_for(findings)

    assert [finding.code for finding in findings] == [expected_code]
    assert escalation is not None
    assert escalation.urgent is urgent


def test_indirect_disordered_eating_signal_escalates_with_policy_order() -> None:
    findings = safety_findings("I have been starving myself and using a laxative.")
    escalation = escalation_for(findings)

    assert [finding.code for finding in findings] == [
        "PURGING_OR_LAXATIVE_USE",
        "SEVERE_FOOD_RESTRICTION",
    ]
    assert escalation is not None
    assert escalation.urgent is False


def test_repeated_case_insensitive_signal_is_deduplicated() -> None:
    findings = safety_findings("Diabetes, DIABETIC, and insulin management")

    assert [finding.code for finding in findings] == ["DIABETES_OR_INSULIN"]


@pytest.mark.parametrize(
    ("context", "expected_code"),
    [
        (SafetyContext(pregnancy_lactation_status="pregnant"), "PREGNANCY_OR_BREASTFEEDING"),
        (SafetyContext(pregnancy_lactation_status="breastfeeding"), "PREGNANCY_OR_BREASTFEEDING"),
        (SafetyContext(pregnancy_lactation_status="pregnant_and_breastfeeding"), "PREGNANCY_OR_BREASTFEEDING"),
        (SafetyContext(medical_conditions=["diabetes"]), "DIABETES_OR_INSULIN"),
        (SafetyContext(medical_conditions=["uses_insulin_or_glucose_lowering_medication"]), "DIABETES_OR_INSULIN"),
        (SafetyContext(medical_conditions=["kidney_disease"]), "KIDNEY_DISEASE"),
        (SafetyContext(medical_conditions=["heart_disease"]), "HEART_DISEASE_OR_HYPERTENSION"),
        (SafetyContext(medical_conditions=["hypertension"]), "HEART_DISEASE_OR_HYPERTENSION"),
        (SafetyContext(medical_conditions=["eating_disorder_history"]), "EATING_DISORDER_HISTORY"),
        (SafetyContext(risk_flags=["under_18"]), "UNDER_18"),
        (SafetyContext(risk_flags=["current_disordered_eating_behaviors"]), "CURRENT_DISORDERED_EATING_BEHAVIORS"),
        (SafetyContext(risk_flags=["chest_pain_or_breathing_difficulty"]), "CHEST_PAIN_OR_BREATHING_DIFFICULTY"),
        (SafetyContext(risk_flags=["fainting_or_severe_dizziness"]), "FAINTING_OR_SEVERE_DIZZINESS"),
        (SafetyContext(risk_flags=["purging_or_laxative_use"]), "PURGING_OR_LAXATIVE_USE"),
        (SafetyContext(risk_flags=["severe_food_restriction"]), "SEVERE_FOOD_RESTRICTION"),
        (SafetyContext(risk_flags=["rapid_weight_loss_request"]), "RAPID_WEIGHT_LOSS_REQUEST"),
        (SafetyContext(risk_flags=["other_medical_condition"]), "OTHER_MEDICAL_CONDITION"),
    ],
)
def test_every_escalating_structured_context_value_maps_to_its_policy_code(
    context: SafetyContext, expected_code: str
) -> None:
    assert [finding.code for finding in safety_findings("", context)] == [expected_code]


@pytest.mark.parametrize("value", ["unknown", "not_pregnant_or_breastfeeding"])
def test_non_escalating_pregnancy_values_do_not_create_a_finding(value: str) -> None:
    assert safety_findings("", SafetyContext(pregnancy_lactation_status=value)) == []


@pytest.mark.parametrize(
    ("phrase", "expected_code"),
    [
        ("shortness of breath", "CHEST_PAIN_OR_BREATHING_DIFFICULTY"),
        ("trouble breathing", "CHEST_PAIN_OR_BREATHING_DIFFICULTY"),
        ("fainting", "FAINTING_OR_SEVERE_DIZZINESS"), ("severe dizziness", "FAINTING_OR_SEVERE_DIZZINESS"),
        ("purging", "PURGING_OR_LAXATIVE_USE"), ("severely restrict food", "SEVERE_FOOD_RESTRICTION"),
        ("eating disorder", "EATING_DISORDER_HISTORY"), ("anorexia", "EATING_DISORDER_HISTORY"),
        ("bulimia", "EATING_DISORDER_HISTORY"), ("binge eating", "EATING_DISORDER_HISTORY"),
        ("pregnancy", "PREGNANCY_OR_BREASTFEEDING"), ("breastfeeding", "PREGNANCY_OR_BREASTFEEDING"),
        ("diabetes", "DIABETES_OR_INSULIN"), ("diabetic", "DIABETES_OR_INSULIN"),
        ("kidney disease", "KIDNEY_DISEASE"), ("heart disease", "HEART_DISEASE_OR_HYPERTENSION"),
        ("heart condition", "HEART_DISEASE_OR_HYPERTENSION"), ("high blood pressure", "HEART_DISEASE_OR_HYPERTENSION"),
        ("hypertension", "HEART_DISEASE_OR_HYPERTENSION"), ("dehydrate", "OTHER_MEDICAL_CONDITION"),
        ("water cut", "OTHER_MEDICAL_CONDITION"), ("rapid water loss", "OTHER_MEDICAL_CONDITION"),
        ("anaphylaxis", "OTHER_MEDICAL_CONDITION"), ("allergic reaction", "OTHER_MEDICAL_CONDITION"),
        ("medication dosage", "OTHER_MEDICAL_CONDITION"), ("medication advice", "OTHER_MEDICAL_CONDITION"),
        ("drug dosage", "OTHER_MEDICAL_CONDITION"), ("drug advice", "OTHER_MEDICAL_CONDITION"),
        ("supplement advice", "OTHER_MEDICAL_CONDITION"),
    ],
)
def test_every_remaining_bounded_message_phrase_maps_to_its_policy_code(
    phrase: str, expected_code: str
) -> None:
    assert [finding.code for finding in safety_findings(f"Please help with {phrase}.")] == [expected_code]


def test_structured_duplicates_collapse_and_findings_use_policy_order() -> None:
    context = SafetyContext(
        medical_conditions=["hypertension", "diabetes", "diabetes"],
        risk_flags=["under_18", "chest_pain_or_breathing_difficulty", "under_18"],
    )

    assert context.medical_conditions == ["hypertension", "diabetes"]
    assert context.risk_flags == ["under_18", "chest_pain_or_breathing_difficulty"]
    assert [finding.code for finding in safety_findings("", context)] == [
        "CHEST_PAIN_OR_BREATHING_DIFFICULTY",
        "DIABETES_OR_INSULIN",
        "HEART_DISEASE_OR_HYPERTENSION",
        "UNDER_18",
    ]


def test_unknown_context_values_are_rejected_and_unknown_does_not_mask_message_signal() -> None:
    with pytest.raises(ValidationError):
        SafetyContext(medical_conditions=["unverified_condition"])
    with pytest.raises(ValidationError):
        SafetyContext(risk_flags=["unverified_flag"])

    assert [finding.code for finding in safety_findings("I am diabetic.", SafetyContext(pregnancy_lactation_status="unknown"))] == ["DIABETES_OR_INSULIN"]


def test_numeric_policy_findings_cover_age_rapid_loss_bmi_and_calorie_floor() -> None:
    underage = TargetInputs(age=17, gender="female", weight_kg=45, height_cm=165, activity_level="light", fitness_goal="maintenance")
    rapid_loss = TargetInputs(age=30, gender="female", weight_kg=60, height_cm=165, activity_level="light", fitness_goal="weight_loss", requested_weekly_loss_kg=0.7)
    class_three = TargetInputs(age=30, gender="male", weight_kg=130, height_cm=170, activity_level="light", fitness_goal="maintenance")

    assert "UNDER_18" in [finding.code for finding in safety_findings("", inputs=underage)]
    assert "RAPID_WEIGHT_LOSS_REQUEST" in [finding.code for finding in safety_findings("", inputs=rapid_loss)]
    assert "BMI_UNDERWEIGHT" in [finding.code for finding in safety_findings("", inputs=underage)]
    assert "BMI_CLASS_III_OBESITY" in [finding.code for finding in safety_findings("", inputs=class_three)]
    assert [finding.code for finding in safety_findings("", inputs=class_three, proposed_calories=1499)] == ["BMI_CLASS_III_OBESITY", "BELOW_MINIMUM_CALORIE_FLOOR"]

@pytest.mark.parametrize(
    ("gender", "calories", "expected"),
    [("female", 1200, []), ("other", 1199, ["BELOW_MINIMUM_CALORIE_FLOOR"]), ("male", 1499, ["BELOW_MINIMUM_CALORIE_FLOOR"]), ("male", 1500, [])],
)
def test_calorie_floor_boundaries_match_policy(gender: str, calories: int, expected: list[str]) -> None:
    inputs = TargetInputs(age=30, gender=gender, weight_kg=60, height_cm=165, activity_level="light", fitness_goal="maintenance")
    assert [finding.code for finding in safety_findings("", inputs=inputs, proposed_calories=calories)] == expected


def test_bmi_and_rapid_loss_threshold_boundaries_match_policy() -> None:
    bmi_40 = TargetInputs(age=30, gender="female", weight_kg=129.61, height_cm=180, activity_level="light", fitness_goal="maintenance")
    bmi_18_5 = TargetInputs(age=30, gender="female", weight_kg=74, height_cm=200, activity_level="light", fitness_goal="maintenance")
    exact_loss = TargetInputs(age=30, gender="female", weight_kg=60, height_cm=165, activity_level="light", fitness_goal="weight_loss", requested_weekly_loss_kg=0.6)
    excessive_loss = exact_loss.model_copy(update={"requested_weekly_loss_kg": 0.601})

    assert "BMI_CLASS_III_OBESITY" in [finding.code for finding in safety_findings("", inputs=bmi_40)]
    assert "BMI_UNDERWEIGHT" not in [finding.code for finding in safety_findings("", inputs=bmi_18_5)]
    assert "RAPID_WEIGHT_LOSS_REQUEST" not in [finding.code for finding in safety_findings("", inputs=exact_loss)]
    assert "RAPID_WEIGHT_LOSS_REQUEST" in [finding.code for finding in safety_findings("", inputs=excessive_loss)]
