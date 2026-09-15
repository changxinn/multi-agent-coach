"""High-confidence prompt-injection and tool-manipulation patterns."""

import re

INJECTION_PATTERN = re.compile(
    r"\b(?:ignore|disregard|override|bypass)\b.{0,80}\b(?:previous|prior|above|"
    r"system|developer|safety|instructions?|rules?)\b|"
    r"\b(?:reveal|show|print|dump|repeat|tell(?: me)?|give(?: me)?|share|provide|display)\b"
    r".{0,80}\b(?:system prompt|developer message|hidden instructions?|api key|secret(?:s)?|token(?:s)?)\b|"
    r"\b(?:what(?:'s| is)|where (?:are|is))\b.{0,80}\b(?:system prompt|developer message|"
    r"hidden instructions?|api key|secret(?:s)?|token(?:s)?)\b|"
    r"\b(?:act as|you are now)\b.{0,80}\b(?:system|developer|administrator|jailbreak)\b",
    re.IGNORECASE | re.DOTALL,
)

TOOL_MANIPULATION_PATTERN = re.compile(
    r"\b(?:call|invoke|run|use|execute)\b.{0,80}\b(?:tool|function|terminal|shell|"
    r"database|sql|api)\b.{0,80}\b(?:without|bypass|ignore|instead of)\b|"
    r"\b(?:delete|drop|exfiltrate)\b.{0,80}\b(?:database|table|file|data|record)\b",
    re.IGNORECASE | re.DOTALL,
)