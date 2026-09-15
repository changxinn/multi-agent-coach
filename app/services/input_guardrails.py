"""Central deterministic gateway for unsafe or unsupported user input."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from app.policies.input_guardrails.injection_patterns_v1 import (
    INJECTION_PATTERN,
    TOOL_MANIPULATION_PATTERN,
)
from app.policies.input_guardrails.policy_v1 import (
    GuardrailAction,
    GuardrailCategory,
    InputGuardrailDecision,
)
from app.policies.input_guardrails.profanity_patterns_v1 import (
    PROFANITY_PATTERN,
    TARGETED_HARASSMENT_PATTERN,
)
from app.policies.input_guardrails.response_templates_v1 import RESPONSE_TEMPLATES
from app.services.llm_guard_secondary import detects_prompt_injection

_ZERO_WIDTH = re.compile(r"[\u200b-\u200d\ufeff]")
_SELF_HARM = re.compile(r"\b(?:kill myself|end my life|suicide|suicidal|hurt myself|self harm)\b", re.IGNORECASE)
_URGENT_MEDICAL = re.compile(r"\b(?:chest pain|can't breathe|cannot breathe|difficulty breathing|unconscious|severe bleeding|stroke|overdose)\b", re.IGNORECASE)
_DISORDERED_EATING = re.compile(r"\b(?:make myself vomit|purge|starve myself|stop eating|how to become anorexic)\b", re.IGNORECASE)
_UNSAFE_EXERCISE = re.compile(r"\b(?:exercise|work\s*out|workout|train|run|lift).{0,60}\b(?:broken|fractured|torn|severe pain|can't bear weight)\b|\b(?:broken|fractured|torn).{0,60}\b(?:exercise|work\s*out|workout|train|run|lift)\b", re.IGNORECASE)
_EXTREME_DIETING = re.compile(r"\b(?:lose|drop)\s+(?:\d{2,}|(?:twenty|thirty|forty))\s+(?:pounds?|lbs?)\s+(?:in|within)\s+(?:a|one)\s+(?:week|month)|\b(?:[0-7]\d\d|zero)\s+calories?\s+(?:a|per)\s+day\b", re.IGNORECASE)
_INJURY_EXERCISE = re.compile(r"\b(?:exercise|work\s*out|workout|train|run|lift).{0,60}\b(?:injur(?:y|ed)|pain|sprain|strain|sore knee|sore back)\b|\b(?:injur(?:y|ed)|pain|sprain|strain|sore knee|sore back).{0,60}\b(?:exercise|work\s*out|workout|train|run|lift)\b", re.IGNORECASE)
_SENSITIVE_DATA = re.compile(r"\b(?:password|social security number|ssn|credit card number|bank account number|api key|private key)\b", re.IGNORECASE)
_SEXUAL_CONTENT = re.compile(r"\b(?:nudes?|porn(?:ography)?|sexual(?:ly)? explicit|sex act)\b", re.IGNORECASE)
_VIOLENCE_WRONGDOING = re.compile(r"\b(?:how to (?:kill|hurt|poison|assault)|make (?:a bomb|explosives?)|steal (?:from|a)|evade police)\b", re.IGNORECASE)
_UNSUPPORTED = re.compile(r"\b(?:write (?:me )?(?:code|an essay)|solve (?:my )?homework|legal advice|trade (?:stocks|crypto)|diagnose my)\b", re.IGNORECASE)


def _decision(action: GuardrailAction, category: GuardrailCategory, rule_id: str) -> InputGuardrailDecision:
    return InputGuardrailDecision(action, category, rule_id, RESPONSE_TEMPLATES[category])


def normalize_input(content: str) -> str:
    """Normalize common obfuscation while retaining text only in process memory."""
    normalized = unicodedata.normalize("NFKC", content).casefold()
    normalized = _ZERO_WIDTH.sub("", normalized)
    normalized = normalized.translate(str.maketrans({"@": "a", "$": "s"}))
    return re.sub(r"\s+", " ", normalized).strip()


def latest_user_message(messages: Iterable[Any]) -> str:
    """Extract the most recent user message, accepting current graph message shapes."""
    for message in reversed(list(messages)):
        if not isinstance(message, dict) or message.get("role") not in {"user", "human"}:
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content.removeprefix("You: ").strip()
    return ""


def evaluate_input(content: str) -> InputGuardrailDecision:
    """Evaluate content using the documented safety-first precedence order."""
    normalized = normalize_input(content)
    if not normalized:
        return InputGuardrailDecision(GuardrailAction.ALLOW)
    if _SELF_HARM.search(normalized):
        return _decision(GuardrailAction.ESCALATE, GuardrailCategory.SELF_HARM, "IGV1-SELF-HARM-001")
    if _URGENT_MEDICAL.search(normalized):
        return _decision(GuardrailAction.ESCALATE, GuardrailCategory.URGENT_MEDICAL, "IGV1-MEDICAL-001")
    if _DISORDERED_EATING.search(normalized):
        return _decision(GuardrailAction.ESCALATE, GuardrailCategory.DISORDERED_EATING, "IGV1-EATING-001")
    if _UNSAFE_EXERCISE.search(normalized):
        return _decision(GuardrailAction.ESCALATE, GuardrailCategory.UNSAFE_EXERCISE, "IGV1-EXERCISE-001")
    if _EXTREME_DIETING.search(normalized):
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.EXTREME_DIETING, "IGV1-DIETING-001")
    if _INJURY_EXERCISE.search(normalized):
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.INJURY_EXERCISE, "IGV1-INJURY-001")
    if _SENSITIVE_DATA.search(normalized):
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.SENSITIVE_DATA, "IGV1-PRIVACY-001")
    if _SEXUAL_CONTENT.search(normalized):
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.SEXUAL_CONTENT, "IGV1-SEXUAL-001")
    if _VIOLENCE_WRONGDOING.search(normalized):
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.VIOLENCE_WRONGDOING, "IGV1-VIOLENCE-001")
    if INJECTION_PATTERN.search(normalized):
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.PROMPT_INJECTION, "IGV1-INJECTION-001")
    secondary_injection = detects_prompt_injection(normalized)
    if secondary_injection is True:
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.PROMPT_INJECTION, "IGV1-INJECTION-002")
    if secondary_injection is None:
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.PROMPT_INJECTION, "IGV1-INJECTION-003")
    if TOOL_MANIPULATION_PATTERN.search(normalized):
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.TOOL_MANIPULATION, "IGV1-TOOLS-001")
    if TARGETED_HARASSMENT_PATTERN.search(normalized):
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.HARASSMENT, "IGV1-HARASSMENT-001")
    if PROFANITY_PATTERN.search(normalized):
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.PROFANITY, "IGV1-PROFANITY-001")
    if _UNSUPPORTED.search(normalized):
        return _decision(GuardrailAction.REDIRECT, GuardrailCategory.UNSUPPORTED, "IGV1-UNSUPPORTED-001")
    return InputGuardrailDecision(GuardrailAction.ALLOW)


def evaluate_latest_user_message(state: dict[str, Any]) -> InputGuardrailDecision:
    """Evaluate exactly the latest user turn, never historical conversation content."""
    return evaluate_input(latest_user_message(state.get("messages", [])))