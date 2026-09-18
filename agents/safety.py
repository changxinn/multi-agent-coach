"""Deterministic safety checks used by the Head Coach before routing."""

import re

from agents.contracts import SafetyDecision

MEDICAL_RISK_PATTERNS = [
    r"\bchest pain\b",
    r"\bcan(?:'|no)t breathe\b",
    r"\bsevere pain\b",
    r"\bdizziness\b",
    r"\bfainting\b",
    r"\bheart attack\b",
    r"\bsuicid",
    r"\bself[- ]harm\b",
]

DISCLAIMER = "This system provides general fitness guidance only, not medical diagnosis or treatment."

INJECTION_MARKERS = [
    "ignore previous instructions",
    "ignore all instructions",
    "system prompt",
    "you are now",
    "reveal your instructions",
    "jailbreak",
    "developer mode",
    "do anything now",
]

MAX_INPUT_CHARS = 4000
ABUSE_PATTERNS = [
    r"\bkill yourself\b",
    r"\bhack (?:into|the)\b",
    r"<script\b",
    r"\bdrop table\b",
    r"\$\{jndi:",
]


def check_input_safety(text: str) -> SafetyDecision:
    normalized = text.strip().lower()
    if not normalized:
        return SafetyDecision(
            allowed=False,
            flags=["empty_input"],
            action="clarify",
            message="Please enter a fitness-related question.",
        )

    if len(text) > MAX_INPUT_CHARS:
        return SafetyDecision(
            allowed=False,
            flags=["input_too_long"],
            action="clarify",
            message="That's a bit long for me to work with — try a shorter question about training, food, or recovery.",
        )

    for pattern in ABUSE_PATTERNS:
        if re.search(pattern, normalized):
            return SafetyDecision(
                allowed=False,
                flags=["blocked_content"],
                action="clarify",
                message=(
                    "I can't help with that. If you have a training, nutrition, or recovery "
                    "question, I'm here for it."
                ),
            )

    for pattern in MEDICAL_RISK_PATTERNS:
        if re.search(pattern, normalized):
            return SafetyDecision(
                allowed=False,
                escalate=True,
                flags=["medical_escalation"],
                action="escalate",
                message=(
                    "Your message may indicate a medical emergency. "
                    "Stop exercising and seek professional medical care immediately. "
                    f"{DISCLAIMER}"
                ),
            )

    flags: list[str] = []
    action = "proceed"
    if _looks_like_prompt_injection(normalized):
        flags.append("prompt_injection_attempt")
        action = "proceed_with_caution"

    return SafetyDecision(
        allowed=True,
        flags=flags,
        action=action,
        message=DISCLAIMER,
    )


def strip_injection_text(text: str) -> str:
    """Keep routing based on the athlete's request, not jailbreak instructions."""
    cleaned = text
    lowered = text.lower()
    for marker in INJECTION_MARKERS:
        index = lowered.find(marker)
        if index != -1:
            cleaned = (cleaned[:index] + " " + cleaned[index + len(marker) :]).strip()
            lowered = cleaned.lower()
    return cleaned.strip() or text


def _looks_like_prompt_injection(text: str) -> bool:
    return any(marker in text for marker in INJECTION_MARKERS)
