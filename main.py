from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from agents import orchestrator
from display import print_backend, print_banner, print_help_hints, print_profile_block
from nodes import (
    check_exit_condition,
    human_node,
    orchestrator_routing,
    specialist_node,
    summarizer_node,
)
from state import State
from tools.storage import load_data, reset_session_logs
from utils import DEBUG

load_dotenv(override=True)


def collect_profile() -> dict:
    """
    Quick onboarding for demo runs. Press Enter to accept defaults.
    """
    data = load_data()
    profile = data.get("profile", {})

    print("  Profile setup (press Enter for defaults)")
    print("  Note: 'exit' only works in the chat prompt below, not here.\n")
    name = input(f"  Name  [{profile.get('name', 'Athlete')}]: ").strip()
    goal = input(f"  Goal  [{profile.get('goal', 'general fitness')}]: ").strip()
    level = input(f"  Level [{profile.get('fitness_level', 'beginner')}]: ").strip()

    return {
        "name": name or profile.get("name", "Athlete"),
        "goal": goal or profile.get("goal", "general fitness"),
        "fitness_level": level or profile.get("fitness_level", "beginner"),
    }


def build_graph():
    """
    Build the LangGraph coaching workflow.
    """
    builder = StateGraph(State)

    builder.add_node("human", human_node)
    builder.add_node("orchestrator", orchestrator)
    builder.add_node("specialist", specialist_node)
    builder.add_node("summarizer", summarizer_node)

    builder.add_edge(START, "human")

    builder.add_conditional_edges(
        "human",
        check_exit_condition,
        {
            "summarizer": "summarizer",
            "orchestrator": "orchestrator",
            "human": "human",
        },
    )

    builder.add_conditional_edges(
        "orchestrator",
        orchestrator_routing,
        {
            "specialist": "specialist",
            "human": "human",
        },
    )

    builder.add_edge("specialist", "orchestrator")
    builder.add_edge("summarizer", END)

    return builder.compile()


def main():
    print_banner()

    if DEBUG:
        print("  Verbose DEBUG is ON (raw LLM traces in .env)\n")
    else:
        print(
            "  Backend trace is ON (routing + tools). Set DEBUG=true for full LLM logs.\n"
        )

    profile = collect_profile()

    reset_session_logs(profile)
    print_backend("Session logs cleared", "fresh workout/meal/sleep tracking", "system")

    print_profile_block(profile)
    print_help_hints()

    print_backend(
        "Starting LangGraph session", "human -> orchestrator -> specialist", "system"
    )

    graph = build_graph()

    initial_state = State(
        messages=[],
        volley_msg_left=0,
        next_agent=None,
        user_profile=profile,
    )

    try:
        graph.invoke(initial_state)
    except KeyboardInterrupt:
        print("\n\n  Session interrupted (Ctrl+C). Goodbye!")
    except Exception as e:
        print(f"\n  An error occurred: {e}")
        print("  Ending session...")


if __name__ == "__main__":
    main()
