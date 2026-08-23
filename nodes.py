from typing import Literal

from agents import specialist, summarizer
from display import (
    print_agent_response,
    print_backend,
    print_summary_block,
    print_user_line,
)
from state import State


def human_node(state: State) -> dict:
    """
    Collect user input and reset the specialist volley counter.
    """
    user_input = input("\n  > ").strip()

    if not user_input:
        print_backend("Empty input ignored", "type a message or 'exit'", "system")
        return {
            "messages": [],
            "volley_msg_left": 0,
            "next_agent": "human",
        }

    if user_input:
        print_user_line(user_input)

    if user_input.strip().lower() == "exit":
        print_backend("Ending session", "generating summary", "system")
    else:
        print_backend("New prompt received", "volley reset to 1", "head_coach")

    human_message = {
        "role": "user",
        "content": f"You: {user_input}",
    }

    return {
        "messages": [human_message],
        "volley_msg_left": 1,
        "next_agent": None,
    }


def check_exit_condition(
    state: State,
) -> Literal["summarizer", "orchestrator", "human"]:
    """
      Route to session summary when the user types exit.
    Empty input loops back to human without calling the LLM.
    """
    messages = state.get("messages", [])
    if not messages:
        return "human"

    last_message = messages[-1]
    content = last_message.get("content", "").replace("You: ", "").strip()

    if content.lower() == "exit":
        return "summarizer"

    return "orchestrator"


def orchestrator_routing(state: State) -> Literal["specialist", "human"]:
    """
    Continue specialist loop or return control to the user.

    Route to specialist when the Head Coach has selected one (next_agent).
    Volley alone is not enough — orchestrator decrements volley before this
    check, so a single-turn reply (volley=1) becomes 0 after routing.
    """
    next_agent = state.get("next_agent")
    volley_left = state.get("volley_msg_left", 0)

    if next_agent and next_agent != "human":
        return "specialist"

    if volley_left > 0:
        return "specialist"
    return "human"


def specialist_node(state: State) -> dict:
    """
    Invoke the selected specialist agent and print its response.
    """
    next_agent = state.get("next_agent", "training_planner")
    agent_label = next_agent.replace("_", " ")

    print_backend("Generating response", f"calling LLM for {agent_label}", next_agent)

    result = specialist(next_agent, state)

    if result and "messages" in result:
        display_text = result.get("display_text", "")
        if display_text:
            print_agent_response(next_agent, display_text)
        else:
            print_backend(
                "No response text", "check DEBUG=true for details", next_agent
            )
        return {"messages": result["messages"]}

    print_backend("Specialist returned no result", agent_key=next_agent)
    return {}


def summarizer_node(state: State) -> dict:
    """
    Generate and display the end-of-session summary.
    """
    print_backend("Generating session summary", agent_key="system")

    summary = summarizer(state)
    print_summary_block(summary)

    return {}
