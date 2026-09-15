"""Narrow patterns for profanity and targeted abuse under input-guardrails-v1."""

import re

PROFANITY_PATTERN = re.compile(
    r"\b(?:fuck(?:ing|er|ed|s)?|shit(?:ty)?|bitch(?:es)?|asshole|bastard|"
    r"cunt|dick|piss(?:ed|ing)?|damn)\b",
    re.IGNORECASE,
)

TARGETED_HARASSMENT_PATTERN = re.compile(
    r"\b(?:you|they|he|she|people|person|coach|trainer)\s+(?:are|is)\s+"
    r"(?:a\s+)?(?:fuck(?:ing|er)?|shit(?:ty)?|bitch|asshole|cunt|dick|bastard)\b|"
    r"\b(?:kill yourself|kys)\b",
    re.IGNORECASE,
)