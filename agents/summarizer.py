import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agents.contracts import SpecialistId
from agents.summarizer_client import SummarizerClient, should_call_summarizer_service
from utils import debug

try:
    from app.config import get_settings

    _settings = get_settings()
    if _settings.OPENAI_API_KEY and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = _settings.OPENAI_API_KEY
except Exception as exc:
    debug(f"Could not load OpenAI key from app.config: {exc}", "SUMMARIZER")


def _load_progress() -> str:
    try:
        from tools import get_progress_summary

        return get_progress_summary()
    except Exception:
        return "No local progress log available."


def _topics_from_state(state: dict) -> str:
    topics: list[str] = []
    for result in state.get("agent_results", []):
        agent = result.get("agent")
        if agent == SpecialistId.TRAINING:
            topics.append("training")
        elif agent == SpecialistId.NUTRITION:
            topics.append("nutrition")
        elif agent == SpecialistId.RECOVERY:
            topics.append("recovery")

    if not topics:
        blob = " ".join(
            str(msg.get("content", "")).lower() for msg in state.get("messages", [])
        )
        if "alex" in blob or "training" in blob or "workout" in blob:
            topics.append("training")
        if "sam" in blob or "nutrition" in blob or "meal" in blob:
            topics.append("nutrition")
        if "jordan" in blob or "sleep" in blob or "recovery" in blob:
            topics.append("recovery")
    return ", ".join(sorted(set(topics))) or "general coaching"


def _format_agent_attribution(state: dict) -> str:
    results = state.get("agent_results") or []
    if results:
        lines = ["Participating agents:"]
        for result in results:
            agent = result.get("agent", "unknown")
            explanation = result.get("explanation") or "Provided specialist guidance."
            lines.append(f"- {agent}: {explanation}")
        return "\n".join(lines)

    names = []
    for message in state.get("messages", []):
        name = message.get("name")
        if name and name not in names and message.get("role") == "assistant":
            names.append(name)
    if not names:
        return "Participating agents: inferred from conversation history."
    return "Participating agents:\n" + "\n".join(f"- {name}" for name in names)


def build_structured_summary(state: dict, progress: str) -> str:
    """Deterministic summary used by tests and as an LLM-failure fallback."""
    profile = state.get("user_profile", {})
    safety_flags = state.get("safety_flags", [])
    attribution = _format_agent_attribution(state)
    topic_text = _topics_from_state(state)

    safety_notice = ""
    if safety_flags:
        safety_notice = (
            "\n\nSafety notice: flags recorded during this session — "
            + ", ".join(safety_flags)
            + ". This is general fitness guidance, not medical advice."
        )

    return (
        "=== SESSION SUMMARY ===\n"
        f"Goal: {profile.get('goal', 'general fitness')}\n"
        f"Level: {profile.get('fitness_level', 'beginner')}\n"
        f"Topics covered: {topic_text}\n\n"
        f"{attribution}\n\n"
        f"{progress}{safety_notice}"
    )


_DAILY_HEADING = re.compile(
    r"^(?:your day at a glance:?\s*)+",
    re.IGNORECASE,
)


def strip_daily_summary_heading(text: str) -> str:
    """Card title already says this; keep only the briefing body."""
    cleaned = text.strip()
    while True:
        next_pass = _DAILY_HEADING.sub("", cleaned, count=1).lstrip("\n").strip()
        if next_pass == cleaned:
            return cleaned
        cleaned = next_pass


def build_daily_summary(state: dict, progress: str) -> str:
    """Short conversational fallback when the LLM is unavailable."""
    return (
        "Easy-to-moderate session today — keep it quality over grind, around RPE 4–6/10 "
        "so you can still talk.\n"
        "Recovery emphasis: keep the work honest and get a solid night of sleep.\n"
        "Fuel: hit 20–30g protein each meal, grab carbs like fruit or grains before you "
        "train, and sip toward 2–3L of water. You got this bestie!"
    )


def _llm_summary(state: dict, progress: str, *, kind: str = "session") -> str | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    messages = state.get("messages", [])
    profile = state.get("user_profile", {})
    conversation_text = "\n".join(str(msg.get("content", "")) for msg in messages)
    if kind == "daily":
        system_prompt = """You are a friendly Head Coach texting the athlete.

Write a SHORT Daily Summary as if you're messaging them. Format exactly like this:

<one or two sentences on today's training focus and effort (RPE)>
Recovery emphasis: <one sentence on recovery/sleep>
Fuel: <one sentence on protein, carbs around the workout, and water>
You got this bestie!

Rules:
- 70 words max
- Do not start with "Your day at a glance" or any heading — the dashboard already has that title
- No markdown headings, no bullet dump, no "Progress Summary"
- No "Head Coach:" prefix
- Conversational, warm, specific"""
        user_prompt = f"""Athlete profile:
Goal: {profile.get("goal", "general fitness")}
Level: {profile.get("fitness_level", "beginner")}

Recent conversation (may be empty):
{conversation_text or "(no chat yet today)"}

Progress notes (use only if useful, do not paste verbatim):
{progress}

Write today's Daily Summary."""
    else:
        system_prompt = """You are the Head Coach wrapping up a coaching session.

Write a concise session summary that includes:
1. Main topics discussed (training, nutrition, recovery)
2. Key advice given by the team
3. Any actions logged or commitments made
4. 1-2 suggested focus areas for tomorrow

Keep it encouraging, practical, and under 200 words."""
        user_prompt = f"""Athlete profile:
Goal: {profile.get("goal", "general fitness")}
Level: {profile.get("fitness_level", "beginner")}

Conversation:
{conversation_text}

Current progress data:
{progress}

Provide the session summary."""
    try:
        llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-5-nano"), temperature=0, timeout=90
        )
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        if isinstance(response.content, list):
            summary = " ".join(str(item) for item in response.content).strip()
        else:
            summary = str(response.content).strip()
        if kind == "daily":
            return strip_daily_summary_heading(summary)
        return f"{summary}\n\n---\n\n{progress}"
    except Exception:
        return None


def summarize_locally(state: dict, progress: str | None = None) -> str:
    kind = state.get("summary_kind", "session")
    progress_text = progress if progress is not None else _load_progress()
    if kind == "daily":
        llm_text = _llm_summary(state, progress_text, kind="daily")
        if llm_text:
            return llm_text
        return build_daily_summary(state, progress_text)

    messages = state.get("messages", [])
    if not messages and not state.get("agent_results"):
        return "No session to summarize."
    llm_text = _llm_summary(state, progress_text, kind="session")
    if llm_text:
        return llm_text
    return build_structured_summary(state, progress_text)


def summarizer(state) -> str:
    """
    End-of-session summary from the Head Coach perspective.
    When USE_SUMMARIZER_SERVICE is set, the API process calls the Summarizer image.
    """
    progress = _load_progress()
    if should_call_summarizer_service():
        try:
            return SummarizerClient().summarize(state, progress)
        except Exception:
            return summarize_locally(state, progress)
    return summarize_locally(state, progress)
