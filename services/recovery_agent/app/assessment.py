"""Deterministic recovery scoring and safety escalation rules."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import RecoveryEvaluateRequest, RecoveryEvaluateResponse


MEDICAL_RISK_PATTERN = re.compile(
    r"\b(chest pain|chest discomfort|difficulty breathing|shortness of breath|"
    r"fainted|fainting|passed out|severe dizziness|dizzy and.*fall|severe swelling)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RecoveryHistory:
    sleep_logs_last_7_days: int = 0
    average_sleep_minutes: float | None = None
    average_sleep_quality: float | None = None
    check_ins_last_7_days: int = 0
    workouts_last_7_days: int = 0


def _extract_sleep_hours(message: str) -> float | None:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s*(?:of\s+)?sleep\b", message, re.I)
    if not match:
        match = re.search(r"\b(?:slept|sleep)\s*(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", message, re.I)
    return float(match.group(1)) if match else None


def _extract_scale(message: str, label: str) -> int | None:
    match = re.search(rf"\b{label}\s*(?:is|was|:)?\s*(10|[1-9])(?:\s*/\s*10)?\b", message, re.I)
    return int(match.group(1)) if match else None


def _quality_from_message(message: str) -> int | None:
    lowered = message.lower()
    if any(word in lowered for word in ("excellent", "great sleep", "slept well")):
        return 5
    if "good" in lowered:
        return 4
    if any(word in lowered for word in ("poor", "terrible", "awful", "restless")):
        return 2
    return None


def assess_recovery(
    request: RecoveryEvaluateRequest,
    history: RecoveryHistory,
) -> RecoveryEvaluateResponse:
    """Score recovery from structured inputs, message signals, and persisted history."""
    from datetime import UTC, datetime

    message = request.message.strip()
    created_at = datetime.now(UTC)
    tool_trace = ["get_recovery_history", "evaluate_fatigue", "assess_sleep_quality"]

    if MEDICAL_RISK_PATTERN.search(message):
        recommendations = [
            "Stop exercising for now and seek urgent medical assessment.",
            "If symptoms are severe or worsening, contact local emergency services.",
        ]
        return RecoveryEvaluateResponse(
            status="escalate",
            score=10,
            message=(
                "- Please stop training for now.\n"
                "- Your reported symptoms need professional medical assessment.\n"
                "Seek urgent care if symptoms are severe, worsening, or return."
            ),
            reasoning="Reported symptoms match the service's medical-risk escalation rules.",
            recommendations=recommendations,
            tool_trace=tool_trace + ["medical_risk_escalation"],
            created_at=created_at,
        )

    sleep_hours = request.sleep_hours if request.sleep_hours is not None else _extract_sleep_hours(message)
    sleep_quality = request.sleep_quality if request.sleep_quality is not None else _quality_from_message(message)
    energy = request.energy if request.energy is not None else _extract_scale(message, "energy")
    soreness = request.soreness if request.soreness is not None else _extract_scale(message, "soreness")
    stress = request.stress if request.stress is not None else _extract_scale(message, "stress")

    if sleep_hours is None and history.average_sleep_minutes is not None:
        sleep_hours = history.average_sleep_minutes / 60
    if sleep_quality is None and history.average_sleep_quality is not None:
        sleep_quality = round(history.average_sleep_quality)

    score = 0
    signals: list[str] = []
    if sleep_hours is not None:
        if sleep_hours <= 5:
            score += 3
            signals.append("very short sleep")
        elif sleep_hours < 7:
            score += 2
            signals.append("below-target sleep")
    if sleep_quality is not None and sleep_quality <= 2:
        score += 2
        signals.append("poor sleep quality")
    if energy is not None and energy <= 3:
        score += 2
        signals.append("low energy")
    if soreness is not None and soreness >= 7:
        score += 2
        signals.append("high soreness")
    if stress is not None and stress >= 8:
        score += 1
        signals.append("high stress")
    if history.workouts_last_7_days >= 5:
        score += 1
        signals.append("high recent training frequency")
        tool_trace.append("calculate_training_load")

    if score >= 6:
        status = "red"
        recommendations = [
            "Take a rest or low-intensity active-recovery day.",
            "Prioritise sleep, hydration, and a normal balanced meal today.",
        ]
        next_step = "Reassess tomorrow before returning to hard training."
    elif score >= 3:
        status = "amber"
        recommendations = [
            "Reduce intensity or volume today and avoid max-effort work.",
            "Use a short walk, mobility, or easy cardio if you want to move.",
        ]
        next_step = "What is your energy level from 1 to 10?"
    else:
        status = "green"
        recommendations = [
            "Your recovery signals support your planned training.",
            "Keep sleep and effort consistent, and log changes early.",
        ]
        next_step = "Log your sleep again tomorrow to keep the trend accurate."

    signal_text = ", ".join(signals) if signals else "no elevated recovery-risk signals"
    message_lines = [f"- {item}" for item in recommendations]
    message_lines.append(next_step)
    return RecoveryEvaluateResponse(
        status=status,
        score=score,
        message="\n".join(message_lines),
        reasoning=f"Assessment based on {signal_text} and recent recovery history.",
        recommendations=recommendations,
        tool_trace=tool_trace,
        created_at=created_at,
    )
