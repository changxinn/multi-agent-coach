"""Deterministic rollout helpers for Nutrition Agent routing."""
from __future__ import annotations

import hashlib

MIN_ROLLOUT_PERCENT = 0
MAX_ROLLOUT_PERCENT = 100
ROLLOUT_PERCENT_ERROR = "NUTRITION_AGENT_ROLLOUT_PERCENT must be an integer from 0 through 100"


def validate_rollout_percent(percent: int) -> int:
    """Validate and return a rollout percentage in the inclusive range 0..100."""
    if isinstance(percent, bool) or not isinstance(percent, int):
        raise TypeError(ROLLOUT_PERCENT_ERROR)
    if percent < MIN_ROLLOUT_PERCENT or percent > MAX_ROLLOUT_PERCENT:
        raise ValueError(ROLLOUT_PERCENT_ERROR)
    return percent


def nutrition_rollout_bucket(user_id: int) -> int:
    """Return a stable rollout bucket for an authenticated numeric user ID.

    The bucket algorithm is intentionally pinned by the Nutrition Agent plan:
    SHA-256(decimal user_id UTF-8), first eight digest bytes as unsigned big-endian,
    modulo 100.
    """
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id must be a positive integer")

    digest = hashlib.sha256(str(user_id).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 100


def is_nutrition_agent_enabled_for_user(user_id: int, percent: int) -> bool:
    """Return whether a user should be routed to the Nutrition Agent service."""
    rollout_percent = validate_rollout_percent(percent)
    if rollout_percent == 0:
        return False
    if rollout_percent == 100:
        return True
    return nutrition_rollout_bucket(user_id) < rollout_percent
