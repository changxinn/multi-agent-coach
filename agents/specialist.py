import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from display import print_backend
from tools import (
    exercise_lookup,
    get_progress_summary,
    log_meal,
    log_sleep,
    log_workout,
)
from tools.log_intent import intents_for_agent
from utils import debug

AGENTS = {
    "training_planner": {
        "name": "Alex (Training Planner)",
        "role": "Certified strength and conditioning coach",
        "personality": "Motivating, structured, focuses on progressive overload and safe form",
        "speech_style": "Clear, actionable, uses sets/reps when helpful",
        "tools": ["log_workout", "exercise_lookup", "progress"],
        "extra_instructions": """
TRAINING-SPECIFIC RULES:
- Tailor every plan to the athlete's stated goal (flexibility, Hyrox, strength, fat loss, etc.)
- When the athlete confirms training days (e.g. "Mon, Wed, Fri, Sun"), output the full weekly plan immediately — each day + focus. Never defer with "I'll add details later."
- For program requests: give a weekly structure (days + focus + key movements). Respect equipment limits and injuries mentioned in the conversation.
- For injury constraints (knee, back, shoulder): prefer low-impact cardio, unilateral work, and controlled range; avoid high-impact running unless cleared.
- On progress check-ins: summarize workouts and training consistency only. Briefly note gaps in meals/sleep and suggest asking Sam or Jordan — do NOT log meals or sleep yourself.
- Never re-log workouts, meals, or sleep from conversation history or progress data — only log what the athlete explicitly asks to log in their latest message.
- When logging a workout: acknowledge the entry, then give one training tip or next-step question.
- One Action per turn only. Do not chain multiple Action lines.
""",
    },
    "nutrition_advisor": {
        "name": "Sam (Nutrition Advisor)",
        "role": "Sports nutrition specialist",
        "personality": "Practical, non-judgmental, emphasizes sustainable habits",
        "speech_style": "Friendly, concrete meal ideas, balances macros simply",
        "tools": ["log_meal", "progress"],
    },
    "recovery_coach": {
        "name": "Jordan (Recovery Coach)",
        "role": "Sleep and recovery specialist",
        "personality": "Calm, evidence-based, prioritizes rest as training",
        "speech_style": "Reassuring, asks about sleep and stress, suggests recovery tactics",
        "tools": ["log_sleep", "progress"],
    },
}

TOOL_DESCRIPTIONS = {
    "log_workout": "Log a workout. Action format: log_workout: 30 min easy run",
    "exercise_lookup": "Look up exercise tips. Action format: exercise_lookup: squat",
    "log_meal": "Log a meal. Action format: log_meal: lunch chicken rice vegetables",
    "log_sleep": "Log sleep. Action format: log_sleep: 7.5 hours, good",
    "progress": "Get progress summary for workouts, meals, and sleep",
}


def execute_tool(tool_name: str, argument: str = "") -> str:
    tool_name = tool_name.lower().strip()
    argument = argument.strip()

    if tool_name == "log_workout":
        if not argument:
            return "Error: provide workout description after log_workout:"
        return log_workout(argument)
    if tool_name == "exercise_lookup":
        if not argument:
            return "Error: provide exercise name after exercise_lookup:"
        return exercise_lookup(argument)
    if tool_name == "log_meal":
        if not argument:
            return "Error: provide meal description after log_meal:"
        return log_meal(argument)
    if tool_name == "log_sleep":
        if not argument:
            return "Error: provide sleep details after log_sleep: e.g. 7.5 hours, good"
        parts = argument.split(",", 1)
        hours = parts[0].strip()
        quality = parts[1].strip() if len(parts) > 1 else "fair"
        return log_sleep(hours, quality)
    if tool_name == "progress":
        return get_progress_summary()

    return f"Unknown tool: {tool_name}"


def _agent_allowed_tool(agent_id: str, tool_name: str) -> bool:
    if agent_id not in AGENTS:
        return False
    return tool_name in AGENTS[agent_id]["tools"]


def _last_user_text(messages: list) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "").replace("You: ", "").strip()
    return ""


def _training_context_hints(agent_id: str, messages: list) -> str:
    """Inject conversation-aware hints so Alex delivers plans instead of deferring."""
    if agent_id != "training_planner":
        return ""

    user_text = _last_user_text(messages)
    if not user_text:
        return ""

    hints: list[str] = []
    lowered = user_text.lower()

    day_tokens = re.findall(
        r"\b(mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:rs(?:day)?)?|"
        r"fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b",
        lowered,
    )
    if day_tokens and len(user_text.split()) <= 12:
        days = ", ".join(day_tokens)
        hints.append(
            f"Athlete confirmed training days ({days}). "
            "Output the full weekly plan now — one bullet per day with focus and key exercises."
        )

    if re.search(r"\bplan\b.*\b(program|week|schedule)\b|\b\d+\s*-?\s*day\b", lowered):
        hints.append(
            "Athlete wants a program. Give weekly structure (days + focus), "
            "respecting equipment and injuries from the conversation."
        )

    if re.search(r"\b(knee|shoulder|back|hip)\b.*\b(injury|hurt|pain|sore)\b", lowered):
        hints.append(
            "Injury mentioned — use exercise_lookup for affected movements if helpful, "
            "then suggest safe alternatives and low-impact options."
        )

    return "\n".join(hints)


def _claims_logged_without_tool(message: str, tools_called: set[str]) -> bool:
    lowered = message.lower()
    if not re.search(r"\blogged\b", lowered):
        return False
    log_tools = {"log_workout", "log_meal", "log_sleep"}
    return not log_tools.intersection(tools_called)


def specialist(agent_id: str, state) -> dict:
    """
    Generate a specialist response using a ReAct loop with tool calling.
    """
    if agent_id not in AGENTS:
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": f"Unknown agent: {agent_id}",
                }
            ]
        }

    agent = AGENTS[agent_id]
    profile = state.get("user_profile", {})
    messages = state.get("messages", [])

    conversation_text = ""
    for msg in messages:
        conversation_text += f"{msg.get('content', '')}\n"

    available_actions = ""
    for tool in agent["tools"]:
        available_actions += f"\n\n{tool}:\n{TOOL_DESCRIPTIONS[tool]}"

    extra = agent.get("extra_instructions", "")

    system_prompt = f"""You are {agent["name"]}, a {agent["role"]}.
Personality: {agent["personality"]}
Speech style: {agent["speech_style"]}
{extra}
Athlete profile:
- Goal: {profile.get("goal", "general fitness")}
- Fitness level: {profile.get("fitness_level", "beginner")}

You are part of a coaching team helping the athlete with training, nutrition, and recovery.

You run in a loop of Thought, Action, Observation.
At the end of the loop you output a Message.

Use Thought to reason about what the athlete needs.
Use Action to call ONE tool listed below when you need real data or to log something.
Only one Action per response — never output multiple Action lines.
Observation will be the tool result — never invent tool output.

Available actions:
{available_actions}

You ONLY have access to the tools listed above. Do not call tools you cannot access.

Action format examples:
Action: progress
Action: log_workout: 20 min walk
Action: exercise_lookup: squat
Action: log_meal: breakfast oats and banana
Action: log_sleep: 8 hours, excellent

After enough information, output:
Message: [Your coaching response]

STRICT RESPONSE RULES (very important):
- Maximum 60 words total
- Use 2-3 short bullet points starting with "• " OR 1-2 short sentences
- Give ONE clear next step or ONE question at the end
- Do NOT repeat advice already given by another coach in the conversation
- Stay strictly in YOUR specialty — defer other topics briefly
- No long paragraphs, no essay-style answers
- For program plans: give weekly structure only (days + focus), not every set/rep detail unless asked

IMPORTANT:
- If the user asks to log something, you MUST call the matching log tool FIRST
- Never say "logged" unless a tool Observation confirms it
- Use progress before giving feedback on trends when helpful
- Never fabricate logged data; rely on Observation or pre-loaded tool results
- Stay in your specialty but acknowledge the bigger picture
"""

    preflight = intents_for_agent(messages, agent_id, agent["tools"])
    preflight_lines = []
    tools_called = set()

    for tool_name, argument in preflight:
        arg_hint = f"{tool_name}: {argument}" if argument else tool_name
        print_backend("Auto-calling tool", arg_hint, agent_id)
        observation = execute_tool(tool_name, argument)
        tools_called.add(tool_name)
        preview = observation.replace("\n", " ")[:80]
        print_backend("Tool result", preview, agent_id)
        preflight_lines.append(f"- {tool_name} -> {observation}")

    internal_context = (
        f"Recent conversation:\n{conversation_text}\n\nRespond as {agent['name']}.\n"
    )

    context_hints = _training_context_hints(agent_id, messages)
    if context_hints:
        internal_context += f"\nContext hints:\n{context_hints}\n"

    if preflight_lines:
        preflight_note = (
            "\nPre-loaded tool results (already saved — do NOT call again):\n"
            + "\n".join(preflight_lines)
        )
        if "progress" in tools_called:
            preflight_note += (
                "\n\nThis is a progress check — summarize training data only. "
                "Do NOT call log_workout, log_meal, or log_sleep.\n"
            )
        elif any(t.startswith("log_") for t in tools_called):
            preflight_note += "\n\nAcknowledge what was logged using the exact data above.\n"
        internal_context += preflight_note

    max_iterations = 5

    for iteration in range(max_iterations):
        debug(f"Iteration {iteration + 1}/{max_iterations}", agent["name"])

        try:
            llm = ChatOpenAI(model="gpt-5-nano", temperature=1, timeout=90)
            response = llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=internal_context),
                ]
            )
            content = str(response.content).strip()
            debug(f"LLM Response:\n{content}\n", agent["name"])

            if "Message:" in content:
                message_match = re.search(r"Message:\s*(.*)", content, re.DOTALL)
                if message_match:
                    final_message = message_match.group(1).strip()
                    debug(f"Final Message: {final_message}", agent["name"])

                    if _claims_logged_without_tool(final_message, tools_called):
                        internal_context += (
                            "\nYou said something was logged but no log tool ran. "
                            "Call the correct log tool first, then reply.\n"
                        )
                        continue

                    print_backend(
                        "Response ready",
                        f"{len(final_message.split())} words",
                        agent_id,
                    )

                    plain_for_history = f"{agent['name']}: {final_message}"
                    return {
                        "display_text": final_message,
                        "messages": [
                            {
                                "role": "assistant",
                                "name": agent["name"],
                                "content": f"\n{plain_for_history}\n\n",
                            }
                        ],
                    }

            if "Action:" in content:
                action_match = re.search(
                    r"Action:\s*(\w+)(?::\s*(.*?))?(?:\n|$)",
                    content,
                    re.DOTALL,
                )
                if action_match:
                    tool_name = action_match.group(1).lower()
                    argument = (action_match.group(2) or "").strip()
                    # Strip accidental chained actions pasted into the argument
                    argument = re.split(r"\n\s*Action:", argument, maxsplit=1)[0].strip()

                    if not _agent_allowed_tool(agent_id, tool_name):
                        observation = f"Access denied: {agent['name']} cannot use tool '{tool_name}'."
                        print_backend("Tool blocked", tool_name, agent_id)
                    else:
                        arg_hint = f"{tool_name}: {argument}" if argument else tool_name
                        print_backend("Calling tool", arg_hint, agent_id)
                        debug(
                            f"Executing tool: {tool_name} | {argument}", agent["name"]
                        )
                        observation = execute_tool(tool_name, argument)
                        tools_called.add(tool_name)
                        preview = observation.replace("\n", " ")[:80]
                        print_backend("Tool result", preview, agent_id)
                        debug(f"Observation: {observation}", agent["name"])

                    internal_context += f"\n{content}\n\nObservation: {observation}\n"
                    continue

            internal_context += f"\n{content}\n"

        except Exception as e:
            debug(f"LLM error: {e}", agent["name"])
            fallback = "Sorry, I hit a snag — could you repeat that?"
            return {
                "display_text": fallback,
                "messages": [
                    {
                        "role": "assistant",
                        "name": agent["name"],
                        "content": f"{agent['name']}: {fallback}",
                    }
                ],
            }

    fallback = "What's your main focus today?"
    return {
        "display_text": fallback,
        "messages": [
            {
                "role": "assistant",
                "name": agent["name"],
                "content": f"{agent['name']}: {fallback}",
            }
        ],
    }
