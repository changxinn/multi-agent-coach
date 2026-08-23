import re


def _last_user_text(messages: list) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "").replace("You: ", "").strip()
    return ""


def parse_user_intents(user_text: str) -> list[tuple[str, str]]:
    """
    Detect tool calls from explicit user phrasing.
    Returns list of (tool_name, argument).
    """
    if not user_text:
        return []

    text = user_text.strip()
    lowered = text.lower()
    intents: list[tuple[str, str]] = []

    workout = re.search(r"log\s+workout[:\s]+(.+)", text, re.IGNORECASE)
    if workout:
        intents.append(("log_workout", workout.group(1).strip().rstrip(".")))

    meal = re.search(r"log\s+meal[:\s]+(.+)", text, re.IGNORECASE)
    if meal:
        intents.append(("log_meal", meal.group(1).strip().rstrip(".")))

    sleep = re.search(r"log\s+sleep[:\s]+(.+)", text, re.IGNORECASE)
    if sleep:
        intents.append(("log_sleep", sleep.group(1).strip().rstrip(".")))

    ate = re.search(
        r"(?:I\s+)?(?:ate|had)\s+(.+?)\s+for\s+(breakfast|lunch|dinner|snack)",
        text,
        re.IGNORECASE,
    )
    if ate and re.search(r"\blog\b", lowered):
        intents.append(("log_meal", f"{ate.group(2).lower()} {ate.group(1).strip()}"))

    if re.search(r"\blog\s+it\b", lowered) and not any(
        i[0] == "log_meal" for i in intents
    ):
        if "mcdonald" in lowered:
            intents.append(("log_meal", "lunch McDonald's"))
        elif ate:
            intents.append(
                ("log_meal", f"{ate.group(2).lower()} {ate.group(1).strip()}")
            )

    slept = re.search(
        r"(?:I\s+)?slept\s+(\d+(?:\.\d+)?)\s*hours?(?:\s*,\s*(.+))?",
        text,
        re.IGNORECASE,
    )
    if slept and re.search(r"\blog\b", lowered):
        quality = (slept.group(2) or "fair").strip()
        intents.append(("log_sleep", f"{slept.group(1)} hours, {quality}"))

    if re.search(
        r"how am i doing|progress this week|my progress|what(?:'s| is) logged",
        lowered,
    ):
        intents.append(("progress", ""))

    form = re.search(
        r"(?:good\s+)?form\s+for\s+(?:a\s+|an\s+)?([a-zA-Z\s\-]+?)(?:\?|$|\.)",
        text,
        re.IGNORECASE,
    )
    if form:
        intents.append(("exercise_lookup", form.group(1).strip()))

    return intents


def intents_for_agent(
    messages: list, agent_id: str, allowed_tools: list[str]
) -> list[tuple[str, str]]:
    """
    Filter parsed intents to tools this agent may call.
    """
    user_text = _last_user_text(messages)
    parsed = parse_user_intents(user_text)
    return [(tool, arg) for tool, arg in parsed if tool in allowed_tools]
