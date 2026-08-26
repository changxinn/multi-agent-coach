"""
Agent service for LangGraph integration.

Wraps LangGraph workflow for API usage.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Import State at module level for LangGraph type inspection
try:
    from state import State
except ImportError:
    # Define a placeholder if state module not available
    State = dict


def build_api_graph():
    """
    Build LangGraph for API usage.

    Similar to CLI version but with API-friendly nodes.

    Returns:
        Compiled LangGraph workflow
    """
    try:
        from langgraph.graph import END, START, StateGraph

        # Import existing components
        from state import State
        from agents import orchestrator as orchestrator_agent

        # Import or create API-friendly nodes
        from app.services.agent_service import (
            human_node_api,
            specialist_node_api,
            check_exit_condition_api,
            orchestrator_routing_api,
        )

        # Build graph
        builder = StateGraph(State)

        # Add nodes
        builder.add_node("human", human_node_api)
        builder.add_node("orchestrator", orchestrator_agent)
        builder.add_node("specialist", specialist_node_api)
        builder.add_node("summarizer", summarizer_node_api)

        # Add edges
        builder.add_edge(START, "human")

        builder.add_conditional_edges(
            "human",
            check_exit_condition_api,
            {
                "summarizer": "summarizer",
                "orchestrator": "orchestrator",
                "human": "human",
            },
        )

        builder.add_conditional_edges(
            "orchestrator",
            orchestrator_routing_api,
            {
                "specialist": "specialist",
                "end": END,
            },
        )

        builder.add_edge("specialist", "orchestrator")
        builder.add_edge("summarizer", END)

        # Compile graph
        graph = builder.compile()

        logger.info("LangGraph built successfully for API usage")
        return graph

    except ImportError as e:
        logger.error("Failed to import LangGraph dependencies: %s", e)
        raise
    except Exception as e:
        logger.error("Failed to build LangGraph: %s", e)
        raise


def human_node_api(state: "State") -> Dict[str, Any]:
    """
    API version of human node.

    Input message is already in state.
    """
    # Message already added by orchestrator
    return {
        "messages": [],
        "volley_msg_left": 1,
        "next_agent": None,
    }


def check_exit_condition_api(state: "State"):
    """
    API version of exit condition check.

    Routes to summarizer if exit requested.
    """
    from typing import Literal

    messages = state.get("messages", [])
    if not messages:
        return "human"

    last_message = messages[-1]
    content = last_message.get("content", "").replace("You: ", "").strip()

    if content.lower() == "exit":
        return "summarizer"

    return "orchestrator"


def orchestrator_routing_api(state: "State"):
    """
    API version of orchestrator routing.
    """
    from typing import Literal

    next_agent = state.get("next_agent")

    if next_agent and next_agent != "human":
        return "specialist"

    return "end"


def specialist_node_api(state: "State") -> Dict[str, Any]:
    """
    API version of specialist node.

    Calls specialist agent and returns result.
    """
    from agents.specialist import specialist
    from app.config import get_settings

    next_agent = state.get("next_agent", "training_planner")
    volley_left = state.get("volley_msg_left", 1)

    logger.info("Calling specialist agent: %s", next_agent)

    settings = get_settings()
    if next_agent == "recovery_coach" and settings.USE_RECOVERY_AGENT_SERVICE:
        try:
            from app.services.recovery_agent_client import recovery_agent_client

            latest_user_message = next(
                (
                    message.get("content", "").replace("You: ", "").strip()
                    for message in reversed(state.get("messages", []))
                    if message.get("role") == "user"
                ),
                "",
            )
            profile = state.get("user_profile", {})
            response = recovery_agent_client.evaluate(
                user_id=int(profile["user_id"]),
                message=latest_user_message,
                profile=profile,
            )
            message_text = response["message"]
            logger.info(
                "Recovery Agent service completed assessment: status=%s score=%s",
                response.get("status"),
                response.get("score"),
            )
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "name": "Jordan (Recovery Coach)",
                        "content": f"Jordan (Recovery Coach): {message_text}",
                        "metadata": {
                            "recovery_status": response.get("status"),
                            "tool_trace": response.get("tool_trace", []),
                        },
                    }
                ],
                "volley_msg_left": max(0, volley_left - 1),
            }
        except Exception as error:
            # The existing in-process agent is a deliberate development fallback.
            logger.exception("Recovery Agent service failed; using local recovery fallback: %s", error)

    result = specialist(next_agent, state)

    # Decrement volley counter to prevent infinite loop
    new_volley = max(0, volley_left - 1)
    logger.info("Specialist responded, volley_msg_left: %d -> %d", volley_left, new_volley)

    if result and "messages" in result:
        return {
            "messages": result["messages"],
            "volley_msg_left": new_volley,
        }

    logger.warning("Specialist returned no result: %s", next_agent)
    return {"volley_msg_left": new_volley}


def summarizer_node_api(state: "State") -> Dict[str, Any]:
    """
    API version of summarizer node.

    Generates session summary.
    """
    from agents.summarizer import summarizer as summarizer_agent

    logger.info("Generating session summary")

    summary = summarizer_agent(state)

    return {
        "messages": [
            {
                "role": "assistant",
                "content": f"Session Summary:\n{summary}",
            }
        ]
    }
