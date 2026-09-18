"""Turn-scoped chat text helpers so replies do not replay prior assistant turns."""

from __future__ import annotations

import re
from typing import Any

SPEAKER_PREFIX = re.compile(
    r"^(?:Head Coach|Alex(?: \([^)]+\))?|Sam(?: \([^)]+\))?|"
    r"Jordan(?: \([^)]+\))?):\s*",
    re.IGNORECASE,
)


def strip_speaker_prefix(content: str) -> str:
    text = content.replace("You: ", "").strip()
    previous = None
    while previous != text:
        previous = text
        text = SPEAKER_PREFIX.sub("", text).strip()
    return text


def new_assistant_messages(
    prior_messages: list[dict[str, Any]],
    result_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep only assistant messages added in this graph turn."""
    prior_count = sum(1 for message in prior_messages if message.get("role") == "assistant")
    assistants = [
        message for message in result_messages if message.get("role") == "assistant"
    ]
    fresh = assistants[prior_count:]
    last_prior = ""
    for message in reversed(prior_messages):
        if message.get("role") == "assistant":
            last_prior = strip_speaker_prefix(str(message.get("content", "")))
            break

    unique: list[dict[str, Any]] = []
    for index, message in enumerate(fresh):
        content = strip_speaker_prefix(str(message.get("content", "")))
        if not content:
            continue
        # LangGraph may replay the previous assistant before the new turn.
        # Keep a repeated reply when it is the only new message (user asked again).
        if content == last_prior and index < len(fresh) - 1:
            continue
        unique.append({**message, "content": content})
    return unique
