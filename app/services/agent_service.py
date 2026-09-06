"""
Agent service for LangGraph integration.

Wraps LangGraph workflow for API usage.
"""
import logging
from typing import Any

from pydantic import ValidationError

from services.nutrition_agent.app.schemas import NutritionProfileUpsert

logger = logging.getLogger(__name__)

# Import State at module level for LangGraph type inspection
try:
    from state import State
except ImportError:
    # Define a placeholder if state module not available
    State = dict


def _nutrition_user_id(profile: object) -> int | None:
    """Return a valid authenticated user ID from graph state, if available."""
    if not isinstance(profile, dict):
        return None
    value = profile.get("user_id")
    if isinstance(value, bool):
        return None
    try:
        user_id = int(value)
    except (TypeError, ValueError):
        return None
    return user_id if user_id > 0 else None


def _nutrition_profile(profile: object) -> dict[str, Any] | None:
    """Validate and allowlist a Nutrition profile before private evaluation."""
    if not isinstance(profile, dict):
        return None
    allowed = {
        "dietary_preference", "dietary_restrictions", "allergies", "meals_per_day",
        "activity_level", "age", "gender", "weight_kg", "height_cm", "timezone",
    }
    try:
        return NutritionProfileUpsert.model_validate(
            {key: value for key, value in profile.items() if key in allowed}
        ).model_dump(mode="json")
    except ValidationError:
        return None


def _is_missing_nutrition_profile(error: object) -> bool:
    """Return whether a Nutrition Agent error represents first-use onboarding."""
    from app.services.nutrition_agent_client import NutritionAgentError

    return (
        isinstance(error, NutritionAgentError)
        and error.status_code == 404
        and error.code == "NUTRITION_PROFILE_NOT_FOUND"
    )


def _nutrition_profile_required_response(volley_left: int) -> dict[str, Any]:
    """Build the safe chat response used before a Nutrition profile exists."""
    message = (
        "Before I can give personalized nutrition guidance, please set up your nutrition "
        "profile. I need your dietary preference, dietary restrictions, food allergies, "
        "meals per day, and IANA timezone (for example, Asia/Singapore)."
    )
    return {
        "messages": [
            {
                "role": "assistant",
                "name": "Sam (Nutrition Advisor)",
                "content": f"Sam (Nutrition Advisor): {message}",
                "metadata": {
                    "nutrition_status": "profile_required",
                    "nutrition_profile_required": True,
                },
            }
        ],
        "volley_msg_left": max(0, volley_left - 1),
    }


def build_api_graph():
    """
    Build LangGraph for API usage.

    Similar to CLI version but with API-friendly nodes.

    Returns:
        Compiled LangGraph workflow
    """
    try:
        from langgraph.graph import END, START, StateGraph

        from agents import orchestrator as orchestrator_agent

        # Import or create API-friendly nodes
        from app.services.agent_service import (
            check_exit_condition_api,
            human_node_api,
            orchestrator_routing_api,
            specialist_node_api,
        )

        # Import existing components
        from state import State

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


def human_node_api(state: "State") -> dict[str, Any]:
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
    next_agent = state.get("next_agent")

    if next_agent and next_agent != "human":
        return "specialist"

    return "end"


async def specialist_node_api(state: "State") -> dict[str, Any]:
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
    
    # Check for recovery coach microservice
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
        except Exception:
            logger.exception("Recovery Agent service failed; using local recovery fallback")
    
    # Check for nutrition agent microservice
    if next_agent == "nutrition_advisor" and settings.USE_NUTRITION_AGENT_SERVICE:
        try:
            from app.services.nutrition_agent_client import nutrition_agent_client
            from app.services.nutrition_rollout import (
                is_nutrition_agent_enabled_for_user,
            )

            latest_user_message = next(
                (
                    message.get("content", "").replace("You: ", "").strip()
                    for message in reversed(state.get("messages", []))
                    if message.get("role") == "user"
                ),
                "",
            )
            user_id = _nutrition_user_id(state.get("user_profile"))

            if user_id is None:
                logger.warning(
                    "Nutrition Agent service skipped because the graph state has no valid user ID"
                )
            elif not is_nutrition_agent_enabled_for_user(
                user_id,
                settings.NUTRITION_AGENT_ROLLOUT_PERCENT,
            ):
                logger.info(
                    "Nutrition Agent service disabled for user bucket; using local nutrition fallback"
                )
            else:
                profile = await nutrition_agent_client.get_profile(user_id)
                nutrition_profile = _nutrition_profile(profile)
                if nutrition_profile is None:
                    logger.warning("Nutrition Agent returned an invalid profile; using local fallback")
                    raise ValueError("Nutrition profile validation failed")
                response = await nutrition_agent_client.evaluate(
                    user_id=user_id,
                    message=latest_user_message,
                    profile=nutrition_profile,
                )
                message_text = response["message"]
                logger.info(
                    "Nutrition Agent service completed assessment: status=%s score=%s",
                    response.get("status"),
                    response.get("score"),
                )
                return {
                    "messages": [
                        {
                            "role": "assistant",
                            "name": "Sam (Nutrition Advisor)",
                            "content": f"Sam (Nutrition Advisor): {message_text}",
                            "metadata": {
                                "nutrition_status": response.get("status"),
                                "safety_findings": response.get("safety_findings", []),
                                "escalation": response.get("escalation"),
                            },
                        }
                    ],
                    "volley_msg_left": max(0, volley_left - 1),
                }

        except Exception as error:
            if _is_missing_nutrition_profile(error):
                logger.info("Nutrition profile is required before chat evaluation")
                return _nutrition_profile_required_response(volley_left)
            # The existing in-process agent is a deliberate development fallback.
            logger.exception("Nutrition Agent service failed; using local nutrition fallback")

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


def summarizer_node_api(state: "State") -> dict[str, Any]:
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
