"""Deterministic input and output guardrails for the coaching workflow."""

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

# Mild, non-targeted profanity is allowed so the athlete can still receive help.
# The coach is reminded to keep the conversation respectful in the final response.
PROFANITY_PATTERNS = [
    r"\bf+u+c+k+(?:ing|ed|er|s)?\b",
    r"\bs+h+i+t+(?:ty)?\b",
    r"\bd+a+m+n+(?:ed|ing)?\b",
]
HATE_OR_HARASSMENT_PATTERNS = [
    r"\b(kill|hurt|attack)\s+(you|him|her|them)\b",
    r"\b(nigger|faggot|kike)\b",
]
SEXUAL_CONTENT_PATTERNS = [
    r"\b(nudes?|porn|sexual(?:ly)? explicit|rape)\b",
]
HARMFUL_WRONGDOING_PATTERNS = [
    r"\b(make|build|buy)\s+(?:a\s+)?bomb\b",
    r"\bhow to (?:hack|steal|poison)\b",
]
UNSAFE_MEDICAL_OUTPUT_PATTERNS = [
    r"\b(?:you have|this is|definitely)\s+(?:a\s+)?(?:heart attack|stroke|fracture|disease)\b",
    r"\b(?:take|stop taking|prescribe)\s+\d+(?:\s*mg)?\b",
]

# High-confidence sensitive-data formats. We intentionally do not persist detected values.
SECRET_PATTERNS = [
    r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----",
    r"\b(?:sk|pk)_[A-Za-z0-9_-]{16,}\b",
    r"\b(?:api[_-]?key|password|passwd|secret|access[_-]?token)\s*[:=]\s*\S+",
]
PII_PATTERNS = [
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    r"\b(?:\+?\d[\d .()-]{7,}\d)\b",
    r"\b(?:\d[ -]*?){13,19}\b",  # payment-card-like sequence
]

RESPECTFUL_LANGUAGE_REMINDER = "Please keep your messages respectful. "
OUTPUT_FALLBACK = (
    "I can only provide respectful, general fitness guidance. "
    "Please rephrase your training, nutrition, or recovery question."
)


def _matches_any(text: str, patterns: list[str], *, flags: int = 0) -> bool:
    return any(re.search(pattern, text, flags) for pattern in patterns)


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

    if _matches_any(text, SECRET_PATTERNS, flags=re.IGNORECASE) or _matches_any(
        text, PII_PATTERNS, flags=re.IGNORECASE
    ):
        return SafetyDecision(
            allowed=False,
            flags=["sensitive_data_detected"],
            action="clarify",
            message=(
                "For your privacy, please don't share passwords, API keys, payment details, "
                "or personal contact information here. Remove those details and resend your fitness question."
            ),
        )

    if _looks_like_prompt_injection(normalized):
        return SafetyDecision(
            allowed=False,
            flags=["prompt_injection_attempt"],
            action="clarify",
            message=(
                "I can't help with requests to override my instructions or reveal internal "
                "system details. I can help with a training, nutrition, or recovery question."
            ),
        )

    if _matches_any(normalized, ABUSE_PATTERNS):
        return SafetyDecision(
            allowed=False,
            flags=["blocked_content"],
            action="clarify",
            message="I can't help with that. I can help with respectful training, nutrition, or recovery questions.",
        )

    if _matches_any(
        normalized,
        HATE_OR_HARASSMENT_PATTERNS
        + SEXUAL_CONTENT_PATTERNS
        + HARMFUL_WRONGDOING_PATTERNS,
    ):
        return SafetyDecision(
            allowed=False,
            flags=["blocked_harmful_content"],
            action="clarify",
            message="I can't help with that. I can help with respectful training, nutrition, or recovery questions.",
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
    if _matches_any(normalized, PROFANITY_PATTERNS):
        flags.append("profanity_detected")
        action = "proceed_with_reminder"

    return SafetyDecision(
        allowed=True,
        flags=flags,
        action=action,
        message=DISCLAIMER,
    )


def check_output_safety(text: str) -> SafetyDecision:
    """Validate model output before it is added to conversation state or returned to clients."""
    normalized = text.strip().lower()
    if _matches_any(normalized, UNSAFE_MEDICAL_OUTPUT_PATTERNS):
        return SafetyDecision(
            allowed=False,
            flags=["unsafe_medical_output"],
            action="replace",
            message=OUTPUT_FALLBACK,
        )
    if _matches_any(
        normalized,
        HATE_OR_HARASSMENT_PATTERNS
        + SEXUAL_CONTENT_PATTERNS
        + HARMFUL_WRONGDOING_PATTERNS,
    ):
        return SafetyDecision(
            allowed=False,
            flags=["unsafe_output"],
            action="replace",
            message=OUTPUT_FALLBACK,
        )
    if _matches_any(text, SECRET_PATTERNS + PII_PATTERNS, flags=re.IGNORECASE):
        return SafetyDecision(
            allowed=True, flags=["sensitive_data_redacted"], action="redact"
        )
    if _matches_any(normalized, PROFANITY_PATTERNS):
        return SafetyDecision(
            allowed=False,
            flags=["unprofessional_output"],
            action="replace",
            message=OUTPUT_FALLBACK,
        )
    return SafetyDecision()


def redact_sensitive_data(text: str) -> str:
    """Remove high-confidence secrets and PII without echoing their values."""
    redacted = text
    for pattern in SECRET_PATTERNS + PII_PATTERNS:
        redacted = re.sub(pattern, "[redacted]", redacted, flags=re.IGNORECASE)
    return redacted


def guard_output_messages(
    messages: list[dict], *, include_respectful_reminder: bool = False
) -> list[dict]:
    """Apply final output controls consistently across API and terminal workflows."""
    guarded_messages: list[dict] = []
    for message in messages:
        guarded = dict(message)
        content = str(guarded.get("content", ""))
        decision = check_output_safety(content)
        if decision.action == "replace":
            content = decision.message or "I can't provide that response."
        elif decision.action == "redact":
            content = redact_sensitive_data(content)

        if include_respectful_reminder:
            content = f"{RESPECTFUL_LANGUAGE_REMINDER}{content}"

        guarded["content"] = content
        metadata = dict(guarded.get("metadata") or {})
        if decision.flags:
            metadata["output_safety_flags"] = decision.flags
        if metadata:
            guarded["metadata"] = metadata
        guarded_messages.append(guarded)
    return guarded_messages


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
