"""Deterministic ``nutrition-safety-v1`` assessment and safety gates."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .schemas import (
    Escalation,
    NutritionEvaluateRequest,
    NutritionEvaluateResponse,
    SafetyContext,
    SafetyFinding,
    TargetInputs,
)

POLICY_VERSION = "nutrition-safety-v1"
DISCLAIMER = "All nutrition advice is for general informational purposes only and does not constitute medical advice. Consult a healthcare provider before making significant dietary changes."
REFERRAL = "I can’t provide a nutrition target or meal plan for this situation. Please seek personalized guidance from a qualified healthcare professional; seek urgent medical care or local emergency services if symptoms are severe or immediate."
ED_REFERRAL = " If this relates to disordered eating or feeling unsafe around food, consider contacting a qualified clinician or an eating-disorder support service in your region."
ORDERED_CODES = ("CHEST_PAIN_OR_BREATHING_DIFFICULTY", "FAINTING_OR_SEVERE_DIZZINESS", "PURGING_OR_LAXATIVE_USE", "SEVERE_FOOD_RESTRICTION", "CURRENT_DISORDERED_EATING_BEHAVIORS", "EATING_DISORDER_HISTORY", "PREGNANCY_OR_BREASTFEEDING", "DIABETES_OR_INSULIN", "KIDNEY_DISEASE", "HEART_DISEASE_OR_HYPERTENSION", "UNDER_18", "RAPID_WEIGHT_LOSS_REQUEST", "OTHER_MEDICAL_CONDITION", "BMI_UNDERWEIGHT", "BMI_CLASS_III_OBESITY", "BELOW_MINIMUM_CALORIE_FLOOR")
ESCALATE_CODES = set(ORDERED_CODES[:13])


@dataclass(frozen=True)
class NutritionHistory:
    meal_logs_last_7_days: int = 0
    average_calories: float | None = None
    adherence_percentage: float | None = None
    macro_adherence_percentages: dict[str, float | None] | None = None


def _has(message: str, *phrases: str) -> bool:
    return any(
        re.search(r"\b" + re.escape(phrase) + r"\b", message, re.IGNORECASE)
        for phrase in phrases
    )


def safety_findings(message: str, context: SafetyContext | None = None, inputs: TargetInputs | None = None, proposed_calories: int | None = None) -> list[SafetyFinding]:
    """Return ordered, deduplicated, privacy-safe policy codes only."""
    context = context or SafetyContext()
    conditions, flags = set(context.medical_conditions), set(context.risk_flags)
    bmi = inputs.weight_kg / (inputs.height_cm / 100) ** 2 if inputs and inputs.height_cm else None
    checks = {
        "CHEST_PAIN_OR_BREATHING_DIFFICULTY": "chest_pain_or_breathing_difficulty" in flags or _has(message, "chest pain", "shortness of breath", "trouble breathing"),
        "FAINTING_OR_SEVERE_DIZZINESS": "fainting_or_severe_dizziness" in flags or _has(message, "fainting", "passed out", "severe dizziness"),
        "PURGING_OR_LAXATIVE_USE": "purging_or_laxative_use" in flags or _has(message, "purging", "laxative"),
        "SEVERE_FOOD_RESTRICTION": "severe_food_restriction" in flags or _has(message, "severely restrict", "starving myself"),
        "CURRENT_DISORDERED_EATING_BEHAVIORS": "current_disordered_eating_behaviors" in flags,
        "EATING_DISORDER_HISTORY": "eating_disorder_history" in conditions or _has(message, "eating disorder", "anorexia", "bulimia", "binge eating"),
        "PREGNANCY_OR_BREASTFEEDING": context.pregnancy_lactation_status in {"pregnant", "breastfeeding", "pregnant_and_breastfeeding"} or _has(message, "pregnant", "pregnancy", "breastfeeding"),
        "DIABETES_OR_INSULIN": bool({"diabetes", "uses_insulin_or_glucose_lowering_medication"} & conditions) or _has(message, "diabetes", "diabetic", "insulin"),
        "KIDNEY_DISEASE": "kidney_disease" in conditions or _has(message, "kidney disease", "renal disease"),
        "HEART_DISEASE_OR_HYPERTENSION": bool({"heart_disease", "hypertension"} & conditions) or _has(message, "heart disease", "heart condition", "high blood pressure", "hypertension"),
        "UNDER_18": "under_18" in flags or bool(inputs and inputs.age < 18),
        "RAPID_WEIGHT_LOSS_REQUEST": "rapid_weight_loss_request" in flags or bool(inputs and inputs.requested_weekly_loss_kg and inputs.requested_weekly_loss_kg > inputs.weight_kg * .01),
        "OTHER_MEDICAL_CONDITION": "other_medical_condition" in flags or _has(message, "dehydrate", "water cut", "rapid water loss", "anaphylaxis", "allergic reaction", "medication dosage", "medication advice", "drug dosage", "drug advice", "supplement dosage", "supplement advice"),
        "BMI_UNDERWEIGHT": bool(bmi and bmi < 18.5), "BMI_CLASS_III_OBESITY": bool(bmi and bmi >= 40),
        "BELOW_MINIMUM_CALORIE_FLOOR": bool(proposed_calories and proposed_calories < (1500 if inputs and inputs.gender == "male" else 1200)),
    }
    return [SafetyFinding(code=code, severity="escalate" if code in ESCALATE_CODES else "warning") for code in ORDERED_CODES if checks[code]]


def escalation_for(findings: list[SafetyFinding]) -> Escalation | None:
    codes = {finding.code for finding in findings}
    if not codes & ESCALATE_CODES:
        return None
    return Escalation(message=REFERRAL + (ED_REFERRAL if codes & {"PURGING_OR_LAXATIVE_USE", "SEVERE_FOOD_RESTRICTION", "CURRENT_DISORDERED_EATING_BEHAVIORS", "EATING_DISORDER_HISTORY"} else ""), urgent=bool(codes & {"CHEST_PAIN_OR_BREATHING_DIFFICULTY", "FAINTING_OR_SEVERE_DIZZINESS"}))


def assess_nutrition(request: NutritionEvaluateRequest, history: NutritionHistory, profile: dict) -> NutritionEvaluateResponse:
    findings = safety_findings(request.message, request.safety_context)
    escalation = escalation_for(findings)
    if escalation:
        return NutritionEvaluateResponse(status="escalate", score=10, message=f"{escalation.message}\n\n*{DISCLAIMER}*", recommendations=["Seek qualified healthcare support."], safety_findings=findings, escalation=escalation, created_at=datetime.now(UTC))
    score = 0 if history.meal_logs_last_7_days >= 7 else 1
    if history.adherence_percentage is not None and history.adherence_percentage < 70:
        score += 1
    if history.macro_adherence_percentages and any(
        value is not None and value < 70
        for value in history.macro_adherence_percentages.values()
    ):
        score += 1
    if findings:
        score = max(score, 6)
    status = "red" if score >= 6 else "amber" if score >= 3 else "green"
    low_macro_adherence = history.macro_adherence_percentages and any(
        value is not None and value < 70
        for value in history.macro_adherence_percentages.values()
    )
    recommendation = (
        "A qualified professional can help tailor a safe approach." if findings
        else "Review your calorie and macronutrient targets across your logged days."
        if low_macro_adherence
        else "Log meals consistently to understand your nutrition patterns." if score
        else "Continue building consistent nutrition habits."
    )
    return NutritionEvaluateResponse(status=status, score=score, message=f"- {recommendation}\n\n*{DISCLAIMER}*", recommendations=[recommendation], safety_findings=findings, created_at=datetime.now(UTC))