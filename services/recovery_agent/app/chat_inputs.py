"""Extract explicitly reported recovery measurements from a chat message."""

from __future__ import annotations

import re

from .schemas import RecoveryEvaluateRequest


def _scale(message: str, label: str, maximum: int) -> int | None:
    match = re.search(
        rf"\b(?:my\s+)?{label}\s*(?:is|was|:|=)?\s*(\d{{1,2}})(?:\s*/\s*{maximum})?(?![\d/])",
        message,
        re.IGNORECASE,
    )
    if not match:
        return None
    value = int(match.group(1))
    return value if 1 <= value <= maximum else None


def _sleep_hours(message: str) -> float | None:
    amount = r"(\d+(?:\.\d+)?)"
    unit = r"(hours?|hrs?|h|minutes?|mins?|m)\b"
    patterns = (
        rf"\b(?:i\s+)?slept\s+(?:for\s+)?{amount}\s*{unit}",
        rf"\b(?:log|logged)\s+(?:my\s+)?sleep\s*(?::|=|for)?\s*{amount}\s*{unit}",
        rf"\b(?:my\s+)?sleep\s*(?:last\s+night\s*)?(?:was|:|=)\s*{amount}\s*{unit}",
        rf"\b(?:got|had)\s+{amount}\s*{unit}\s+of\s+sleep\b",
    )
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            hours = value / 60 if match.group(2).lower().startswith("m") else value
            return hours if 0 <= hours <= 24 else None
    return None


def chat_measurements(request: RecoveryEvaluateRequest) -> RecoveryEvaluateRequest:
    """Fill missing structured fields only from numeric values the athlete supplied."""
    parsed = {
        "sleep_hours": _sleep_hours(request.message),
        "sleep_quality": _scale(request.message, "(?:sleep\\s+)?quality", 5),
        "energy": _scale(request.message, "energy", 10),
        "soreness": _scale(request.message, "soreness", 10),
        "stress": _scale(request.message, "stress", 10),
    }
    return request.model_copy(
        update={
            name: value
            for name, value in parsed.items()
            if getattr(request, name) is None and value is not None
        }
    )
