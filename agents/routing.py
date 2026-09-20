"""Deterministic Head Coach routing used by the in-process node and the HTTP service."""

import re

from agents.contracts import VALID_SPECIALISTS, RoutingDecision, SpecialistId

PROMPT_VERSION = "head-coach-routing-v1"

NUTRITION_REQUEST_TERMS = re.compile(
    r"\b(?:food|meal|breakfast|lunch|dinner|snack|diet|protein|calories?|"
    r"macros?|hydration|fuel(?:ing)?|ate|eat|eating)\b",
    re.IGNORECASE,
)

TRAINING_KEYWORDS = (
    "workout",
    "exercise",
    "train",
    "gym",
    "squat",
    "deadlift",
    "run",
    "lift",
    "rep",
    "set",
    "form",
    "program",
    "hyrox",
)
NUTRITION_KEYWORDS = (
    "meal",
    "food",
    "eat",
    "diet",
    "protein",
    "calorie",
    "macro",
    "hydration",
    "lunch",
    "breakfast",
    "dinner",
)
RECOVERY_KEYWORDS = (
    "sleep",
    "rest",
    "sore",
    "fatigue",
    "tired",
    "recovery",
    "burnout",
    "stress",
    "nap",
)

CLARIFY_PROMPT = "Happy to help. Is this about training, food, or recovery?"
CHITCHAT_PROMPT = (
    "Hey, I'm here. Want to talk training, food, sleep, or something else on your mind?"
)
IDENTITY_PROMPT = (
    "I'm your Head Coach. I keep things in one place while Alex handles training, "
    "Sam covers meals and fueling, and Jordan looks after sleep and recovery. "
    "We can chat, and I'm most useful when you bring a gym, food, or rest question. "
    "What do you need?"
)
IDENTITY_RE = re.compile(
    r"(who are you|who you are|what are you|who is this|what can you do|"
    r"what's your name|whats your name|tell me about yourself|introduce yourself|"
    r"your team|which agents?|what do you do)",
    re.IGNORECASE,
)
SMALLTALK_RE = re.compile(
    r"\b(hi|hey|hello|yo|sup|thanks|thank you|good morning|good evening|"
    r"how are you|what's up|whats up)\b",
    re.IGNORECASE,
)


def parse_llm_agents(raw: str) -> list[SpecialistId]:
    tokens = re.split(r"[\s,;/]+", raw.strip().lower())
    agents: list[SpecialistId] = []
    for token in tokens:
        if token in VALID_SPECIALISTS:
            specialist = SpecialistId(token)
            if specialist not in agents:
                agents.append(specialist)
    return agents


def heuristic_route(text: str) -> RoutingDecision:
    """Keyword routing with a nutrition-first rule that matches the nutrition-agent branch."""
    normalized = text.strip()
    if not normalized:
        return RoutingDecision(
            agents=[],
            reason="Missing user message.",
            confidence=0.0,
            needs_clarification=True,
            clarification_prompt=CLARIFY_PROMPT,
        )

    if NUTRITION_REQUEST_TERMS.search(normalized):
        return RoutingDecision(
            agents=[SpecialistId.NUTRITION],
            reason="Latest message is a nutrition request.",
            confidence=0.86,
        )

    lowered = normalized.lower()
    if IDENTITY_RE.search(normalized):
        return RoutingDecision(
            agents=[],
            reason="Identity question; Head Coach introduces the team.",
            confidence=0.95,
            needs_clarification=True,
            clarification_prompt=IDENTITY_PROMPT,
        )
    if SMALLTALK_RE.search(normalized) and not any(
        keyword in lowered
        for keyword in TRAINING_KEYWORDS + NUTRITION_KEYWORDS + RECOVERY_KEYWORDS
    ):
        return RoutingDecision(
            agents=[],
            reason="Greeting or small talk; Head Coach stays in conversation.",
            confidence=0.7,
            needs_clarification=True,
            clarification_prompt=CHITCHAT_PROMPT,
        )

    selected: list[SpecialistId] = []
    if any(keyword in lowered for keyword in TRAINING_KEYWORDS):
        selected.append(SpecialistId.TRAINING)
    if any(keyword in lowered for keyword in NUTRITION_KEYWORDS):
        selected.append(SpecialistId.NUTRITION)
    if any(keyword in lowered for keyword in RECOVERY_KEYWORDS):
        selected.append(SpecialistId.RECOVERY)

    if not selected:
        if re.search(r"\b(progress|how am i doing|check[- ]?in)\b", lowered):
            return RoutingDecision(
                agents=[SpecialistId.TRAINING],
                reason="Progress check-in defaulted to training planner.",
                confidence=0.6,
            )
        return RoutingDecision(
            agents=[],
            reason="No clear training, nutrition, or recovery topic detected.",
            confidence=0.3,
            needs_clarification=True,
            clarification_prompt=CLARIFY_PROMPT,
        )

    return RoutingDecision(
        agents=selected[:1],
        reason="Matched specialist keywords in the latest user message.",
        confidence=0.75,
    )


def latest_user_message(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = str(message.get("content", ""))
            return content.removeprefix("You: ").strip()
    if messages:
        content = str(messages[-1].get("content", ""))
        return content.removeprefix("You: ").strip()
    return ""
