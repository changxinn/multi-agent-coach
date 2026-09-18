"""Head Coach service logic wraps the shared routing module."""

from agents.orchestrator import route_locally

from .schemas import RouteRequest, RouteResponse


def route(payload: RouteRequest) -> RouteResponse:
    result = route_locally(
        {
            "messages": payload.messages,
            "user_profile": payload.user_profile,
            "volley_msg_left": payload.volley_msg_left,
            "session_id": payload.session_id,
            "trace_id": payload.trace_id,
        }
    )
    return RouteResponse(
        next_agent=result.get("next_agent") or "human",
        selected_agent=result.get("selected_agent"),
        volley_msg_left=result.get("volley_msg_left", 0),
        routing_reason=result.get("routing_reason"),
        needs_clarification=result.get("needs_clarification", False),
        safety_flags=result.get("safety_flags", []),
        messages=result.get("messages", []),
    )
