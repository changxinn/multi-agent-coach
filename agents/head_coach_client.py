"""HTTP client for the Head Coach microservice. Used only by the API process."""

from __future__ import annotations

import os
from typing import Any

import httpx


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def should_call_head_coach_service() -> bool:
    if _flag("HEAD_COACH_SERVICE_MODE"):
        return False
    return _flag("USE_HEAD_COACH_SERVICE")


class HeadCoachClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("HEAD_COACH_URL", "http://localhost:8002").rstrip("/")
        self.token = os.getenv("INTERNAL_SERVICE_TOKEN", "")

    def route(self, state: dict[str, Any]) -> dict[str, Any]:
        if not self.token:
            raise RuntimeError(
                "INTERNAL_SERVICE_TOKEN is required for the Head Coach service"
            )

        response = httpx.post(
            f"{self.base_url}/v1/head-coach/route",
            headers={"X-Internal-Service-Token": self.token},
            json={
                "messages": state.get("messages", []),
                "user_profile": state.get("user_profile", {}),
                "volley_msg_left": state.get("volley_msg_left", 0),
                "session_id": state.get("session_id"),
                "trace_id": state.get("trace_id"),
            },
            timeout=30,
        )
        response.raise_for_status()
        return graph_update_from_route_payload(response.json())


def graph_update_from_route_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep prior routing fields when the service omits them on return-to-user."""
    update: dict[str, Any] = {
        "next_agent": payload["next_agent"],
        "volley_msg_left": payload["volley_msg_left"],
        "needs_clarification": payload.get("needs_clarification", False),
        "safety_flags": payload.get("safety_flags") or [],
    }
    if payload.get("routing_reason") is not None:
        update["routing_reason"] = payload["routing_reason"]
    if payload.get("selected_agent"):
        update["selected_agent"] = payload["selected_agent"]
    messages = payload.get("messages")
    if messages:
        update["messages"] = messages
    return update
