import os
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from display import AGENT_META, print_backend
from utils import debug

_NUTRITION_REQUEST_TERMS = re.compile(
    r"\b(?:food|meal|breakfast|lunch|dinner|snack|diet|protein|calories?|"
    r"macros?|hydration|fuel(?:ing)?)\b",
    re.IGNORECASE,
)
_EXPLICIT_TRAINING_PLAN_TERMS = re.compile(
    r"\b(?:workout|training|exercise|gym)\s+(?:plan|program|routine|schedule)\b|"
    r"\b(?:plan|program|routine|schedule)\b.*\b(?:workout|training|exercise|gym)\b",
    re.IGNORECASE,
)
_ENDURANCE_ACTIVITY_TERMS = re.compile(
    r"\b(?:cardio|run(?:ning)?|jog(?:ging)?|cycl(?:e|ing)|sw(?:im|am|imming)|"
    r"row(?:ing)?|endurance)\b",
    re.IGNORECASE,
)
_RESISTANCE_ACTIVITY_TERMS = re.compile(
    r"\b(?:strength(?:\s+training)?|weight(?:s|lifting)?|resistance(?:\s+training)?|"
    r"lift(?:ing|ed)?|bodyweight)\b",
    re.IGNORECASE,
)
_COMPLETED_ACTIVITY_TERMS = re.compile(
    r"\b(?:did|went|completed|finished|had)\b|\b(?:earlier|today|yesterday|after work)\b",
    re.IGNORECASE,
)


class NutritionFollowUpClassification(BaseModel):
    """Bounded semantic decision for an immediate meal-related follow-up."""

    specialist: Literal["training_planner", "nutrition_advisor", "recovery_coach"]
    nutrition_follow_up: Literal["none", "revise_recent_meal"]
    activity_type: Literal["resistance", "endurance", "mixed", "unspecified"]


class RoutingDecision(BaseModel):
    """Bounded Head Coach decision to delegate or answer without a specialist."""

    route: Literal["specialist", "direct_response"]
    specialist: Literal["training_planner", "nutrition_advisor", "recovery_coach"] | None = None
    response: str | None = None


_VALID_SPECIALISTS = {"training_planner", "nutrition_advisor", "recovery_coach"}
_VALID_FOLLOW_UPS = {"none", "revise_recent_meal"}
_VALID_ACTIVITY_TYPES = {"resistance", "endurance", "mixed", "unspecified"}
_DIRECT_RESPONSE_FALLBACK = (
    "Hi! I can help with workout planning, nutrition, recovery, and progress tracking. "
    "What would you like to work on today?"
)
_INTERNAL_ROUTING_PREFIX = re.compile(
    r"^\s*(?:routing decision\s*:\s*direct[ _]response\.\s*)?"
    r"(?:i(?:'|’)?ll respond directly(?: in chat)?\.\s*)",
    re.IGNORECASE,
)


def _latest_user_message(messages: list[dict]) -> str:
    """Return the latest user-authored text without the display prefix."""
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", "")).removeprefix("You: ").strip()
    return ""


def _previous_user_message(messages: list[dict]) -> str:
    """Return the immediately preceding user message, if the latest user turn has one."""
    user_messages = [
        str(message.get("content", "")).removeprefix("You: ").strip()
        for message in messages
        if message.get("role") == "user"
    ]
    return user_messages[-2] if len(user_messages) >= 2 else ""


def _deterministic_specialist(messages: list[dict]) -> str | None:
    """Route explicit nutrition requests without an LLM."""
    latest_message = _latest_user_message(messages)
    if _NUTRITION_REQUEST_TERMS.search(latest_message):
        return "nutrition_advisor"
    return None


def _reported_activity_type(message: str) -> str | None:
    """Return a clear completed-activity category without inferring ambiguous exercise."""
    if not _COMPLETED_ACTIVITY_TERMS.search(message):
        return None
    has_endurance = bool(_ENDURANCE_ACTIVITY_TERMS.search(message))
    has_resistance = bool(_RESISTANCE_ACTIVITY_TERMS.search(message))
    if has_endurance and has_resistance:
        return "mixed"
    if has_endurance:
        return "endurance"
    if has_resistance:
        return "resistance"
    return None


def _nutrition_follow_up(messages: list[dict]) -> dict | None:
    """Route clear activity updates or classify ambiguous immediate meal follow-ups."""
    latest_message = _latest_user_message(messages)
    previous_message = _previous_user_message(messages)
    if (
        not latest_message
        or _EXPLICIT_TRAINING_PLAN_TERMS.search(latest_message)
        or not _NUTRITION_REQUEST_TERMS.search(previous_message)
    ):
        return None

    if activity_type := _reported_activity_type(latest_message):
        return {
            "nutrition_follow_up": "revise_recent_meal",
            "activity_type": activity_type,
        }

    try:
        from app.config import get_settings

        model = get_settings().LLM_MODEL
    except Exception:
        model = "gpt-5-nano"

    prompt = """Classify the latest user message in the immediate context of a prior meal request.
Return only the requested schema.
- specialist must be training_planner, nutrition_advisor, or recovery_coach.
- nutrition_follow_up is revise_recent_meal only when the latest message semantically reports
  completed physical activity and should revise the immediately preceding meal request. Otherwise none.
- A clear cardio, run, cycling, swimming, strength, weights, or resistance-training update immediately
  after a meal request is meal context unless the user explicitly asks for a training plan.
- activity_type is resistance, endurance, mixed, or unspecified.
- An explicit request for a workout plan, program, routine, or schedule is training_planner and none.
Do not infer medical facts or nutrition facts."""
    try:
        classified = ChatOpenAI(model=model, temperature=0, timeout=30).with_structured_output(
            NutritionFollowUpClassification
        ).invoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(
                    content=(
                        f"Prior user meal request: {previous_message}\n"
                        f"Latest user message: {latest_message}"
                    )
                ),
            ]
        )
        if not isinstance(classified, NutritionFollowUpClassification):
            return None
        if (
            classified.specialist not in _VALID_SPECIALISTS
            or classified.nutrition_follow_up not in _VALID_FOLLOW_UPS
            or classified.activity_type not in _VALID_ACTIVITY_TYPES
        ):
            return None
        if (
            classified.specialist == "nutrition_advisor"
            and classified.nutrition_follow_up == "revise_recent_meal"
        ):
            return {
                "nutrition_follow_up": classified.nutrition_follow_up,
                "activity_type": classified.activity_type,
            }
    except Exception:
        debug("Nutrition follow-up classification unavailable; failing closed", "HEAD COACH")
    return None


def _direct_response_result(response: str, volley_left: int) -> dict:
    """Return a Head Coach message and terminate this graph turn."""
    return {
        "messages": [
            {
                "role": "assistant",
                "name": "Head Coach",
                "content": f"Head Coach: {response}",
            }
        ],
        "next_agent": "human",
        "volley_msg_left": max(0, volley_left - 1),
    }


def _user_visible_direct_response(response: str) -> str:
    """Remove known leading orchestration narration from a direct user reply."""
    return _INTERNAL_ROUTING_PREFIX.sub("", response).strip()

# Load API key from config if available
try:
    from app.config import get_settings
    _settings = get_settings()
    if _settings.OPENAI_API_KEY and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = _settings.OPENAI_API_KEY
except Exception:
    debug("Application settings unavailable while loading the OpenAI key", "HEAD COACH")


def orchestrator(state):
    """
      Head Coach: route the conversation to the best specialist agent.
    Updates next_agent and decrements volley_msg_left.
    """
    volley_left = state.get("volley_msg_left", 0)
    debug(f"Volley messages left: {volley_left}", "HEAD COACH")

    if volley_left <= 0:
        debug("No volleys left, returning to user", "HEAD COACH")
        return {
            "next_agent": "human",
            "volley_msg_left": 0,
        }

    messages = state.get("messages", [])
    profile = state.get("user_profile", {})

    deterministic_selection = _deterministic_specialist(messages)
    if deterministic_selection:
        debug(f"Deterministic nutrition selection: {deterministic_selection}", "HEAD COACH")
        agent_label = AGENT_META.get(deterministic_selection, {}).get(
            "short_name", deterministic_selection
        )
        print_backend(
            "Routing to specialist",
            f"{agent_label} ({deterministic_selection})",
            "head_coach",
        )
        return {
            "next_agent": deterministic_selection,
            "volley_msg_left": volley_left - 1,
        }

    nutrition_follow_up = _nutrition_follow_up(messages)
    if nutrition_follow_up:
        debug("Semantic nutrition follow-up selected", "HEAD COACH")
        return {
            "next_agent": "nutrition_advisor",
            "nutrition_follow_up": nutrition_follow_up,
            "volley_msg_left": volley_left - 1,
        }

    conversation_text = ""
    for msg in messages:
        conversation_text += f"{msg.get('content', '')}\n"

    profile_text = (
        f"Goal: {profile.get('goal', 'general fitness')}, "
        f"Level: {profile.get('fitness_level', 'beginner')}"
    )

    system_prompt = """You are the Head Coach of a fitness coaching team.
Decide whether to delegate a clearly scoped request to a specialist or respond directly.

Available specialists:
- training_planner: Workout plans, exercise form, logging workouts, training load
- nutrition_advisor: Meals, macros, hydration, fueling for training, logging meals
- recovery_coach: Sleep, rest days, soreness, stress, logging sleep

Routing rules:
- Training, workouts, exercises, gym, equipment, injuries affecting training -> training_planner
- Food, meals, diet, protein, calories, hydration, fast food -> nutrition_advisor
- Sleep, tired, soreness recovery, rest days, stress, burnout -> recovery_coach
- Progress check-ins ("how am I doing", "my progress") -> training_planner if workout-focused, nutrition_advisor if food-focused, recovery_coach if sleep-focused; default training_planner
- Otherwise, multi-topic messages: pick the PRIMARY topic in the user's LATEST message
- Do NOT send recovery_coach for equipment or program questions
- Do NOT send training_planner for pure nutrition questions
- Use direct_response for greetings, acknowledgements, small talk, unclear requests, or messages that do not need a specialist. For unclear requests, briefly ask what the athlete would like help with.
- Never restart with a greeting or generic menu when the recent conversation establishes an active topic.
- A direct response must be concise and conversational. Do not provide medical guidance, a workout prescription, or personalized nutrition advice directly.
- The response field is shown verbatim to the athlete. Never mention routing, a routing decision, direct_response, delegation, specialists, or internal chat/orchestration.
- For route=specialist, provide a valid specialist and no response.
- For route=direct_response, provide a non-empty response and no specialist.
"""

    user_prompt = f"""Athlete profile: {profile_text}

Recent conversation:
{conversation_text}

Return the routing decision."""

    debug("Analyzing user intent...", "HEAD COACH")
    print_backend("Analyzing intent", "calling LLM", "head_coach")
    try:
        from app.config import get_settings

        model = get_settings().LLM_MODEL
        decision = ChatOpenAI(model=model, temperature=0, timeout=90).with_structured_output(
            RoutingDecision
        ).invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        if not isinstance(decision, RoutingDecision):
            raise TypeError("Routing model returned an invalid structured decision")
    except Exception:
        debug("Routing model unavailable or invalid; asking for clarification", "HEAD COACH")
        return _direct_response_result(_DIRECT_RESPONSE_FALLBACK, volley_left)

    if decision.route == "direct_response":
        response = _user_visible_direct_response((decision.response or "").strip())
        if response and decision.specialist is None:
            debug("Head Coach responding directly", "HEAD COACH")
            return _direct_response_result(response, volley_left)
        debug("Invalid direct Head Coach response; asking for clarification", "HEAD COACH")
        return _direct_response_result(_DIRECT_RESPONSE_FALLBACK, volley_left)

    selected = decision.specialist
    if selected not in _VALID_SPECIALISTS or decision.response is not None:
        debug("Invalid specialist routing decision; asking for clarification", "HEAD COACH")
        return _direct_response_result(_DIRECT_RESPONSE_FALLBACK, volley_left)

    debug(
        f"Final selection: {selected} (volley {volley_left} -> {volley_left - 1})",
        "HEAD COACH",
    )

    agent_label = AGENT_META.get(selected, {}).get("short_name", selected)
    print_backend(
        "Routing to specialist",
        f"{agent_label} ({selected})",
        "head_coach",
    )

    return {
        "next_agent": selected,
        "volley_msg_left": volley_left - 1,
    }
