"""Optional LLM Guard prompt-injection scanner for ambiguous input only."""

from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Callable

LOGGER = logging.getLogger(__name__)
_ENABLED_VALUES = {"1", "true", "yes", "on"}


def llm_guard_enabled() -> bool:
    """Return whether the optional secondary scanner is explicitly enabled."""
    return os.getenv("INPUT_GUARDRAILS_LLM_GUARD_ENABLED", "false").casefold() in _ENABLED_VALUES


def is_secondary_scan_candidate(normalized_input: str) -> bool:
    """Limit optional ML scanning to requests plausibly targeting instructions or internals."""
    terms = (
        "prompt",
        "instruction",
        "system",
        "developer",
        "hidden",
        "secret",
        "jailbreak",
        "private",
        "direction",
        "guide",
    )
    return any(term in normalized_input for term in terms)


def _prompt_injection_scanner() -> Callable[[str], tuple[str, bool, float]]:
    """Load LLM Guard lazily so it remains an optional deployment dependency."""
    try:
        scanners = importlib.import_module("llm_guard.input_scanners")
        return scanners.PromptInjection().scan
    except (ImportError, AttributeError) as error:
        raise RuntimeError("LLM Guard PromptInjection scanner is unavailable") from error


def detects_prompt_injection(normalized_input: str) -> bool | None:
    """Return a finding, or ``None`` when optional scanning cannot be completed.

    LLM Guard's prompt scanner returns ``(sanitized_prompt, is_valid, risk_score)``;
    an invalid prompt is treated as a prompt-injection finding. Input remains in memory
    only and is never logged here.
    """
    if not llm_guard_enabled() or not is_secondary_scan_candidate(normalized_input):
        return False

    try:
        _, is_valid, _ = _prompt_injection_scanner()(normalized_input)
        return not is_valid
    except Exception:
        LOGGER.warning("Optional LLM Guard secondary scan failed", exc_info=True)
        return None