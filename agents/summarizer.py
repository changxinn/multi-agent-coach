from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from tools import get_progress_summary


def summarizer(state) -> str:
    """
    End-of-session summary from the Head Coach perspective.
    """
    messages = state.get("messages", [])
    profile = state.get("user_profile", {})

    if not messages:
        return "No session to summarize."

    conversation_text = ""
    for msg in messages:
        conversation_text += f"{msg.get('content', '')}\n"

    progress = get_progress_summary()

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
        llm = ChatOpenAI(model="gpt-5-nano", temperature=1, timeout=90)
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

        return f"{summary}\n\n---\n\n{progress}"

    except Exception:
        return f"Session ended with {len(messages)} messages exchanged.\n\n{progress}"
