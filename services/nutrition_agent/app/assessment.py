"""Deterministic nutrition scoring and ethical safeguards."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .schemas import NutritionEvaluateRequest, NutritionEvaluateResponse


# ===========================================
# SAFETY THRESHOLDS (Evidence-based)
# ===========================================

# Minimum safe calories per day (per clinical guidelines)
MIN_CALORIES_WOMEN = 1200
MIN_CALORIES_MEN = 1500

# Maximum safe weight loss: 0.5-1.0 kg/week
MAX_SAFE_WEIGHT_LOSS_PER_WEEK = 1.0

# BMI thresholds (WHO classification)
BMI_UNDERWEIGHT = 18.5
BMI_OBESE_CLASS_III = 40.0

# Eating disorder keyword detection (based on NEDA guidelines)
EATING_DISORDER_KEYWORDS = [
    # Restrictive behaviors
    "starving myself",
    "fasting for days",
    "only eating",
    "afraid to eat",
    "scared to eat",
    "guilt after eating",
    "guilty after eating",
    "purging",
    "vomiting after meals",
    "make myself vomit",
    "laxatives",
    "diet pills",
    "weight loss pills",
    "excessive exercise",
    "over-exercising",

    # Body dysmorphia
    "feel fat",
    "hate my body",
    "disgusted by food",
    "body hatred",

    # Obsessive behaviors
    "counting every calorie",
    "obsessed with calories",
    "terrified of gaining weight",
    "afraid of gaining weight",
    "restricting entire food groups",
]

# Medical risk phrases
MEDICAL_RISK_PHRASES = [
    "chest pain",
    "chest discomfort",
    "difficulty breathing",
    "shortness of breath",
    "fainted",
    "fainting",
    "passed out",
    "severe dizziness",
    "heart palpitations",
    "irregular heartbeat",
]


@dataclass(frozen=True)
class NutritionHistory:
    """7-day nutrition history."""

    meal_logs_last_7_days: int = 0
    average_calories: float | None = None
    average_protein_g: float | None = None
    average_carbs_g: float | None = None
    average_fat_g: float | None = None
    adherence_percentage: float | None = None


def _extract_calories_from_message(message: str) -> int | None:
    """Extract calorie mentions from user message."""
    match = re.search(r"\b(\d{3,4})\s*(?:calories?|cals?|kcal)\b", message, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_meal_frequency(message: str) -> int | None:
    """Extract meal frequency mentions."""
    match = re.search(r"\b(\d)\s*(?:meals?|times)\s*(?:per|a)\s*day\b", message, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _check_eating_disorder_keywords(message: str) -> list[str]:
    """Check for eating disorder warning signs."""
    message_lower = message.lower()
    detected = []
    for keyword in EATING_DISORDER_KEYWORDS:
        if keyword in message_lower:
            detected.append(keyword)
    return detected


def _check_medical_risk(message: str) -> list[str]:
    """Check for medical risk phrases requiring escalation."""
    message_lower = message.lower()
    detected = []
    for phrase in MEDICAL_RISK_PHRASES:
        if phrase in message_lower:
            detected.append(phrase)
    return detected


def _calculate_bmi(weight_kg: float | None, height_cm: float | None) -> float | None:
    """Calculate BMI from weight and height."""
    if not weight_kg or not height_cm or height_cm <= 0:
        return None
    height_m = height_cm / 100
    return round(weight_kg / (height_m ** 2), 1)


def assess_nutrition(
    request: NutritionEvaluateRequest,
    history: NutritionHistory,
    user_profile: dict,
) -> NutritionEvaluateResponse:
    """
    Score nutrition status from structured inputs, message signals, and history.

    Scoring:
    - 0-2: green (on track)
    - 3-5: amber (minor gaps)
    - 6-8: red (major issues)
    - 9+: escalate (medical/professional referral needed)
    """
    message = request.message.strip()
    created_at = datetime.now(UTC)
    tool_trace = ["get_nutrition_history", "calculate_adherence", "assess_macro_balance"]

    # ===========================================
    # IMMEDIATE ESCALATION CHECKS
    # ===========================================

    # 1. Medical risk symptoms
    medical_risks = _check_medical_risk(message)
    if medical_risks:
        return NutritionEvaluateResponse(
            status="escalate",
            score=10,
            message=(
                "- Your reported symptoms require medical attention.\n"
                "- Please consult a healthcare provider before continuing.\n"
                "- This system cannot provide medical diagnosis or treatment."
            ),
            reasoning=f"Medical risk phrases detected: {', '.join(medical_risks)}",
            recommendations=[
                "Stop any extreme dietary practices immediately",
                "Consult a healthcare provider for proper evaluation",
                "If symptoms are severe, seek urgent medical care",
            ],
            tool_trace=tool_trace + ["medical_risk_escalation"],
            created_at=created_at,
        )

    # 2. Eating disorder keywords
    ed_keywords = _check_eating_disorder_keywords(message)
    if ed_keywords:
        return NutritionEvaluateResponse(
            status="escalate",
            score=10,
            message=(
                "- I'm concerned about your relationship with food.\n"
                "- Please consider speaking with a healthcare provider.\n"
                "- You deserve support in developing a healthy approach to nutrition."
            ),
            reasoning=f"Eating disorder warning signs detected: {', '.join(ed_keywords)}",
            recommendations=[
                "Contact a healthcare provider specializing in eating behaviors",
                "Consider resources from National Eating Disorders Association (NEDA)",
                "This system cannot provide medical diagnosis or treatment",
            ],
            tool_trace=tool_trace + ["eating_disorder_screening"],
            created_at=created_at,
        )

    # ===========================================
    # EXTRACT SIGNALS FROM MESSAGE
    # ===========================================

    reported_calories = _extract_calories_from_message(message)
    meal_frequency = _extract_meal_frequency(message)

    # Get user demographics for safety checks
    gender = user_profile.get("gender", "other").lower()
    weight_kg = user_profile.get("weight_kg")
    height_cm = user_profile.get("height_cm")
    fitness_goal = user_profile.get("fitness_goal", "maintenance")

    # ===========================================
    # BMI SAFETY CHECK
    # ===========================================

    bmi = _calculate_bmi(weight_kg, height_cm)
    if bmi is not None:
        if bmi < BMI_UNDERWEIGHT:
            tool_trace.append("bmi_underweight_check")
            # Underweight - already concerning, but not immediate escalation
            # unless combined with other factors
        elif bmi > BMI_OBESE_CLASS_III:
            tool_trace.append("bmi_obese_class_3_check")
            # Class III obesity - recommend medical supervision

    # ===========================================
    # CALORIE SAFETY CHECK
    # ===========================================

    score = 0
    signals: list[str] = []
    recommendations: list[str] = []

    # Check if reported calories are dangerously low
    if reported_calories is not None:
        min_safe_calories = MIN_CALORIES_WOMEN if gender == "female" else MIN_CALORIES_MEN

        if reported_calories < min_safe_calories:
            score += 4
            signals.append(f"very low calorie intake ({reported_calories} < {min_safe_calories})")
            recommendations.append(
                f"Your reported intake is below safe minimums ({min_safe_calories} kcal/day). "
                "This can lead to nutrient deficiencies and metabolic slowdown."
            )
            tool_trace.append("safety_check_calories")
        elif reported_calories < min_safe_calories + 200:
            score += 2
            signals.append(f"low calorie intake ({reported_calories})")
            recommendations.append(
                f"Consider increasing intake to at least {min_safe_calories} kcal/day for safety."
            )

    # ===========================================
    # MEAL LOGGING CONSISTENCY
    # ===========================================

    if history.meal_logs_last_7_days > 0:
        # Good logging consistency
        if history.meal_logs_last_7_days >= 14:  # 2 meals/day average
            signals.append("excellent meal logging consistency")
        elif history.meal_logs_last_7_days >= 7:  # 1 meal/day average
            signals.append("good meal logging consistency")
        else:
            score += 1
            signals.append("inconsistent meal logging")
            recommendations.append("Try logging all meals daily for better tracking.")
    else:
        score += 1
        signals.append("no recent meal logs")
        recommendations.append("Start logging meals to track your nutrition patterns.")

    # ===========================================
    # ADHERENCE TO TARGETS (if available)
    # ===========================================

    if history.adherence_percentage is not None:
        if history.adherence_percentage < 50:
            score += 2
            signals.append(f"low adherence to targets ({history.adherence_percentage:.0f}%)")
            recommendations.append("Focus on meeting your nutrition targets consistently.")
        elif history.adherence_percentage < 70:
            score += 1
            signals.append(f"moderate adherence ({history.adherence_percentage:.0f}%)")

    # ===========================================
    # DETERMINE STATUS
    # ===========================================

    if score >= 6:
        status = "red"
        if not recommendations:
            recommendations = [
                "Your nutrition patterns show significant gaps.",
                "Consider consulting a registered dietitian for personalized guidance.",
            ]
        next_step = "Let's work together to improve your nutrition approach."

    elif score >= 3:
        status = "amber"
        if not recommendations:
            recommendations = [
                "Minor gaps detected in your nutrition approach.",
                "Small adjustments can help you reach your goals more effectively.",
            ]
        next_step = "What aspect of your nutrition would you like to improve?"

    else:
        status = "green"
        if not recommendations:
            recommendations = [
                "Your nutrition approach appears well-balanced.",
                "Continue tracking and maintaining consistent habits.",
            ]
        next_step = "Keep up the great work with your nutrition tracking!"

    # ===========================================
    # BUILD RESPONSE
    # ===========================================

    signal_text = ", ".join(signals) if signals else "no elevated nutrition-risk signals"

    message_lines = [f"- {item}" for item in recommendations[:2]]  # Max 2 bullet points
    message_lines.append(next_step)

    return NutritionEvaluateResponse(
        status=status,
        score=score,
        message="\n".join(message_lines),
        reasoning=f"Assessment based on {signal_text} and recent nutrition history.",
        recommendations=recommendations,
        tool_trace=tool_trace,
        created_at=created_at,
    )
