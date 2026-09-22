import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.contracts import RoutingDecision
from agents.head_coach_client import HeadCoachClient, should_call_head_coach_service
from agents.routing import (
    CLARIFY_PROMPT,
    PROMPT_VERSION,
    heuristic_route,
    latest_user_message,
    parse_llm_agents,
)
from agents.safety import check_input_safety, strip_injection_text
from display import AGENT_META, print_backend
from utils import debug

try:
    from app.config import get_settings

    _settings = get_settings()
    if _settings.OPENAI_API_KEY and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = _settings.OPENAI_API_KEY
except Exception:
    debug("Could not load OpenAI key from app.config", "HEAD COACH")

SYSTEM_PROMPT = """You are the Head Coach of a fitness coaching team.
Your job is to decide which specialist should respond next.

Available specialists:
- training_planner: Workout plans, exercise form, logging workouts, training load
- nutrition_advisor: Meals, macros, hydration, fueling for training, logging meals
- recovery_coach: Sleep, rest days, soreness, stress, logging sleep

Routing rules:
- Training, workouts, exercises, gym, equipment, injuries affecting training -> training_planner
- Food, meals, diet, protein, calories, hydration, fast food -> nutrition_advisor
- Sleep, tired, soreness recovery, rest days, stress, burnout -> recovery_coach
- Progress check-ins ("how am I doing", "my progress") -> training_planner if workout-focused, nutrition_advisor if food-focused, recovery_coach if sleep-focused; default training_planner
- Multi-topic messages: pick the PRIMARY topic in the user's LATEST message only
- Do NOT send recovery_coach for equipment or program questions
- Do NOT send training_planner for pure nutrition questions
- If the message is ambiguous, respond with exactly: CLARIFY

Respond with ONLY one specialist ID or CLARIFY.
"""


def _route_with_llm(
    profile_text: str, conversation_text: str, user_message: str
) -> str:
    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-5-nano"), temperature=0, timeout=90
    )
    user_prompt = f"""Athlete profile: {profile_text}

Recent conversation:
{conversation_text}

Latest user message:
{user_message}

Which specialist should speak next?"""
    response = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
    )
    if isinstance(response.content, list):
        return " ".join(str(item) for item in response.content).strip()
    return str(response.content).strip()


def decide_routing(state: dict, *, use_llm: bool = True):
    """Return a validated routing decision. Never uses random fallback."""
    messages = state.get("messages", [])
    profile = state.get("user_profile", {})
    user_message = strip_injection_text(latest_user_message(messages))
    heuristic = heuristic_route(user_message)
    if heuristic.needs_clarification and heuristic.confidence >= 0.7:
        return heuristic

    profile_text = (
        f"Goal: {profile.get('goal', 'general fitness')}, "
        f"Level: {profile.get('fitness_level', 'beginner')}"
    )
    conversation_text = "\n".join(str(msg.get("content", "")) for msg in messages)

    if use_llm and os.getenv("OPENAI_API_KEY"):
        try:
            debug("Analyzing user intent...", "HEAD COACH")
            print_backend("Analyzing intent", "calling LLM", "head_coach")
            raw = _route_with_llm(profile_text, conversation_text, user_message).lower()
            debug(f"LLM routing raw: {raw}", "HEAD COACH")
            if raw == "clarify" or raw.startswith("clarify"):
                return RoutingDecision(
                    agents=[],
                    reason="LLM requested clarification for an ambiguous message.",
                    confidence=0.5,
                    needs_clarification=True,
                    clarification_prompt=CLARIFY_PROMPT,
                )
            agents = parse_llm_agents(raw)
            if agents:
                return RoutingDecision(
                    agents=agents[:1],
                    reason="LLM selected a specialist for the latest message.",
                    confidence=0.9,
                )
        except Exception as exc:
            debug(f"LLM routing failed, using heuristic: {exc}", "HEAD COACH")

    debug(
        f"Heuristic routing: {[agent.value for agent in heuristic.agents]}",
        "HEAD COACH",
    )
    return heuristic


def route_locally(state: dict) -> dict:
    """In-process Head Coach node compatible with the existing LangGraph."""
    volley_left = state.get("volley_msg_left", 0)
    debug(f"Volley messages left: {volley_left}", "HEAD COACH")

    if volley_left <= 0:
        debug("No volleys left, returning to user", "HEAD COACH")
        return {"next_agent": "human", "volley_msg_left": 0}

    user_message = latest_user_message(state.get("messages", []))
    safety = check_input_safety(user_message)
    if safety.action in {"escalate", "clarify"} and not safety.allowed:
        message = safety.message or "Unable to process this request safely."
        print_backend("Safety gate", safety.action, "head_coach")
        return {
            "next_agent": "human",
            "selected_agent": "human",
            "volley_msg_left": 0,
            "safety_flags": safety.flags,
            "respectful_language_reminder": "profanity_detected" in safety.flags,
            "routing_reason": safety.action,
            "messages": [
                {
                    "role": "assistant",
                    "name": "Head Coach",
                    "content": message,
                }
            ],
        }

    decision = decide_routing(state)
    if decision.needs_clarification:
        prompt = decision.clarification_prompt or "Please clarify your question."
        print_backend("Routing needs clarification", prompt, "head_coach")
        return {
            "next_agent": "human",
            "selected_agent": "human",
            "volley_msg_left": 0,
            "routing_reason": decision.reason,
            "needs_clarification": True,
            "safety_flags": safety.flags,
            "respectful_language_reminder": False,
            "prompt_versions": {"head_coach": PROMPT_VERSION},
            "messages": [
                {
                    "role": "assistant",
                    "name": "Head Coach",
                    "content": (
                        "Please keep your messages respectful. " + prompt
                        if "profanity_detected" in safety.flags
                        else prompt
                    ),
                }
            ],
        }

    selected = decision.agents[0].value
    agent_label = AGENT_META.get(selected, {}).get("short_name", selected)
    print_backend("Routing to specialist", f"{agent_label} ({selected})", "head_coach")
    return {
        "next_agent": selected,
        "selected_agent": selected,
        "volley_msg_left": volley_left - 1,
        "routing_reason": decision.reason,
        "needs_clarification": False,
        "safety_flags": safety.flags,
        "respectful_language_reminder": "profanity_detected" in safety.flags,
        "prompt_versions": {"head_coach": PROMPT_VERSION},
    }


def orchestrator(state):
    """
    Head Coach: route the conversation to the best specialist agent.
    When USE_HEAD_COACH_SERVICE is set, the API process calls the Head Coach image.
    """
    if should_call_head_coach_service():
        try:
            return HeadCoachClient().route(state)
        except Exception as exc:
            debug(
                f"Head Coach service failed; using local routing: {exc}", "HEAD COACH"
            )
    return route_locally(state)
