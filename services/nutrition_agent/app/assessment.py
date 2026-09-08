"""Deterministic ``nutrition-safety-v1`` assessment and safety gates."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .schemas import (
    Escalation,
    MealRecommendation,
    NutritionEvaluateRequest,
    NutritionEvaluateResponse,
    SafetyContext,
    SafetyFinding,
    TargetInputs,
)
from .tools.meal_planner import select_meal

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
    message = re.sub(r"[-‐‑–—]", " ", message)
    return any(
        re.search(r"\b" + re.escape(phrase) + r"\b", message, re.IGNORECASE)
        for phrase in phrases
    )


@dataclass(frozen=True)
class MealRequirements:
    """Deterministic meal constraints parsed from a user request."""

    meal_types: tuple[str, ...]
    max_calories: int | None
    min_protein_g: int
    min_carbs_g: int
    min_fiber_g: int
    min_fat_g: int
    max_fat_g: int | None
    requested_nutrients: tuple[str, ...]
    prioritize_fiber: bool


_NUTRIENT_ALIASES = {
    "protein": ("protein",),
    "carbohydrates": ("carbs", "carbohydrates"),
    "fiber": ("fiber", "fibre"),
    "fat": ("fat", "fats"),
}


def _gram_bound(message: str, nutrient: str, direction: str) -> int | None:
    aliases = "|".join(re.escape(alias) for alias in _NUTRIENT_ALIASES[nutrient])
    if direction == "minimum":
        pattern = rf"(?:at least|minimum|min\.?|over|more than)\s*(\d+)\s*g?\s*(?:of\s+)?(?:{aliases})\b"
    else:
        pattern = rf"(?:under|below|less than|maximum|max\.?)\s*(\d+)\s*g?\s*(?:of\s+)?(?:{aliases})\b"
    match = re.search(pattern, message, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _meal_requirements(message: str) -> MealRequirements | None:
    """Parse supported meal and nutrient constraints without using generated text."""
    named_meal_type = next(
        (meal_type for meal_type in ("breakfast", "lunch", "dinner", "snack") if _has(message, meal_type)),
        None,
    )
    balanced_intent = _has(message, "balanced meal", "balanced")
    high_protein_intent = _has(message, "high protein", "high-protein")
    meal_option_intent = _has(
        message,
        "meal option",
        "food option",
        "dinner option",
        "lunch option",
        "breakfast option",
        "snack option",
        "suggest dinner",
        "suggest lunch",
        "suggest breakfast",
        "suggest a snack",
        "what should i eat",
        "something for dinner",
        "something for lunch",
        "something for breakfast",
        "something to eat",
    )
    requested = tuple(
        nutrient for nutrient, aliases in _NUTRIENT_ALIASES.items() if _has(message, *aliases)
    )
    if not requested and not balanced_intent and not high_protein_intent and not meal_option_intent:
        return None

    # A balanced meal uses documented baseline thresholds for all four macros.
    if balanced_intent:
        requested = tuple(dict.fromkeys((*requested, "protein", "carbohydrates", "fiber", "fat")))
    if high_protein_intent and "protein" not in requested:
        requested = (*requested, "protein")

    calorie_match = re.search(r"(?:under|below|less than|max(?:imum)? of?)\s*(\d+)\s*(?:calories?|cals?|kcal)\b", message, re.IGNORECASE)
    protein_minimum = _gram_bound(message, "protein", "minimum")
    carbs_minimum = _gram_bound(message, "carbohydrates", "minimum")
    fiber_minimum = _gram_bound(message, "fiber", "minimum")
    fat_minimum = _gram_bound(message, "fat", "minimum")
    fat_maximum = _gram_bound(message, "fat", "maximum")
    return MealRequirements(
        meal_types=(named_meal_type,) if named_meal_type else ("breakfast", "lunch", "dinner"),
        max_calories=int(calorie_match.group(1)) if calorie_match else None,
        min_protein_g=protein_minimum or (30 if high_protein_intent else 18 if balanced_intent else 0),
        min_carbs_g=carbs_minimum or (30 if balanced_intent else 0),
        min_fiber_g=fiber_minimum or (8 if balanced_intent else 0),
        min_fat_g=fat_minimum or 0,
        max_fat_g=fat_maximum,
        requested_nutrients=requested,
        prioritize_fiber=balanced_intent or "fiber" in requested,
    )


def _format_meal_recommendation(meal: MealRecommendation) -> str:
    facts = [f"about {meal.calories} calories"]
    nutrient_values = {
        "protein": f"{meal.protein_g} g protein",
        "carbohydrates": f"{meal.carbs_g} g carbohydrates",
        "fiber": f"{meal.fiber_g} g fiber",
        "fat": f"{meal.fat_g} g fat",
    }
    facts.extend(nutrient_values[nutrient] for nutrient in meal.satisfies)
    return f"**{meal.name}**: {', '.join(facts[:-1])}, and {facts[-1]}." if len(facts) > 1 else f"**{meal.name}**: {facts[0]}."


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


def _meal_recommendation_request(
    message: str, profile: dict
) -> tuple[list[str], list[MealRecommendation]] | None:
    """Select trusted meal options and legacy display strings from parsed constraints."""
    requirements = _meal_requirements(message)
    if requirements is None:
        return None
    constraint_description = ", ".join(requirements.requested_nutrients) or "requested"
    recommendations: list[str] = []
    meal_recommendations: list[MealRecommendation] = []
    for meal_type in requirements.meal_types:
        meal = select_meal(
            meal_type,
            str(profile.get("dietary_preference", "omnivore")),
            max_calories=requirements.max_calories,
            min_protein_g=requirements.min_protein_g,
            min_carbs_g=requirements.min_carbs_g,
            min_fiber_g=requirements.min_fiber_g,
            min_fat_g=requirements.min_fat_g,
            max_fat_g=requirements.max_fat_g,
            prioritize_fiber=requirements.prioritize_fiber,
            allergies=profile.get("allergies") or [],
            dietary_restrictions=profile.get("dietary_restrictions") or [],
        )
        if meal is None:
            recommendations.append(
                f"I couldn’t find a {meal_type} template that safely meets the requested {constraint_description} constraints."
            )
            continue
        meal_recommendation = MealRecommendation(
            meal_type=meal_type,
            name=meal["name"],
            calories=meal["calories"],
            protein_g=meal["protein_g"],
            carbs_g=meal["carbs_g"],
            fiber_g=meal["fiber_g"],
            fat_g=meal["fat_g"],
            satisfies=list(requirements.requested_nutrients),
        )
        meal_recommendations.append(meal_recommendation)
        recommendations.append(_format_meal_recommendation(meal_recommendation))
    return recommendations, meal_recommendations


def assess_nutrition(request: NutritionEvaluateRequest, history: NutritionHistory, profile: dict) -> NutritionEvaluateResponse:
    findings = safety_findings(request.message, request.safety_context)
    escalation = escalation_for(findings)
    if escalation:
        return NutritionEvaluateResponse(status="escalate", score=10, message=f"{escalation.message}\n\n*{DISCLAIMER}*", recommendations=["Seek qualified healthcare support."], safety_findings=findings, escalation=escalation, created_at=datetime.now(UTC))
    meal_request = _meal_recommendation_request(request.message, profile)
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
    if meal_request:
        recommendations, meal_recommendations = meal_request
        return NutritionEvaluateResponse(
            status=status,
            score=score,
            message=f"{'\n'.join(f'- {item}' for item in recommendations)}\n\n*{DISCLAIMER}*",
            recommendations=recommendations,
            meal_recommendations=meal_recommendations,
            safety_findings=findings,
            created_at=datetime.now(UTC),
        )
    return NutritionEvaluateResponse(status=status, score=score, message=f"- {recommendation}\n\n*{DISCLAIMER}*", recommendations=[recommendation], safety_findings=findings, created_at=datetime.now(UTC))