"""Types and stable identifiers for the input-guardrails-v1 policy."""

from dataclasses import dataclass
from enum import StrEnum

POLICY_VERSION = "input-guardrails-v1"


class GuardrailAction(StrEnum):
    ALLOW = "allow"
    REDIRECT = "redirect"
    ESCALATE = "escalate"


class GuardrailCategory(StrEnum):
    SELF_HARM = "self_harm"
    URGENT_MEDICAL = "urgent_medical"
    DISORDERED_EATING = "disordered_eating"
    UNSAFE_EXERCISE = "unsafe_exercise"
    EXTREME_DIETING = "extreme_dieting"
    INJURY_EXERCISE = "injury_exercise"
    SENSITIVE_DATA = "sensitive_data"
    SEXUAL_CONTENT = "sexual_content"
    VIOLENCE_WRONGDOING = "violence_wrongdoing"
    PROMPT_INJECTION = "prompt_injection"
    TOOL_MANIPULATION = "tool_manipulation"
    HARASSMENT = "harassment"
    PROFANITY = "profanity"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class InputGuardrailDecision:
    """A deterministic decision with no raw user content in its metadata."""

    action: GuardrailAction
    category: GuardrailCategory | None = None
    rule_id: str | None = None
    response: str | None = None

    @property
    def metadata(self) -> dict[str, str]:
        if self.action is GuardrailAction.ALLOW:
            return {}
        return {
            "input_guardrail_category": str(self.category),
            "input_guardrail_action": str(self.action),
            "input_guardrail_rule_id": str(self.rule_id),
            "input_guardrail_policy_version": POLICY_VERSION,
        }