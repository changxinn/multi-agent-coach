import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from display import AGENT_META, print_backend
from utils import debug

_NUTRITION_REQUEST_TERMS = re.compile(
    r"\b(?:food|meal|breakfast|lunch|dinner|snack|diet|protein|calories?|"
    r"macros?|hydration|fuel(?:ing)?)\b",
    re.IGNORECASE,
)


def _latest_user_message(messages: list[dict]) -> str:
    """Return the latest user-authored text without the display prefix."""
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", "")).removeprefix("You: ").strip()
    return ""


def _deterministic_specialist(latest_message: str) -> str | None:
    """Route explicit meal requests without letting incidental training context win."""
    if _NUTRITION_REQUEST_TERMS.search(latest_message):
        return "nutrition_advisor"
    return None

# Load API key from config if available
try:
    from app.config import get_settings
    _settings = get_settings()
    if _settings.OPENAI_API_KEY and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = _settings.OPENAI_API_KEY
except Exception:
    pass


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

    deterministic_selection = _deterministic_specialist(_latest_user_message(messages))
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

    conversation_text = ""
    for msg in messages:
        conversation_text += f"{msg.get('content', '')}\n"

    profile_text = (
        f"Goal: {profile.get('goal', 'general fitness')}, "
        f"Level: {profile.get('fitness_level', 'beginner')}"
    )

    system_prompt = """You are the Head Coach of a fitness coaching team.
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

Respond with ONLY one specialist ID: training_planner, nutrition_advisor, or recovery_coach.
"""

    user_prompt = f"""Athlete profile: {profile_text}

Recent conversation:
{conversation_text}

Which specialist should speak next?"""

    debug("Analyzing user intent...", "HEAD COACH")
    print_backend("Analyzing intent", "calling LLM", "head_coach")

    valid_agents = ["training_planner", "nutrition_advisor", "recovery_coach"]

    try:
        llm = ChatOpenAI(model="gpt-5-nano", temperature=1, timeout=90)
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )

        if isinstance(response.content, list):
            selected = " ".join(str(item) for item in response.content).strip().lower()
        else:
            selected = str(response.content).strip().lower()

        debug(f"LLM selected: {selected}", "HEAD COACH")

        if selected not in valid_agents:
            import random

            selected = random.choice(valid_agents)
            debug(f"Invalid agent, fallback to: {selected}", "HEAD COACH")

    except Exception:
        import random

        selected = random.choice(valid_agents)
        debug(f"LLM error, random selection: {selected}", "HEAD COACH")

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
