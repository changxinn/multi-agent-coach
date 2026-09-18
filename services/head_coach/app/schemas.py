from typing import Any

from pydantic import BaseModel, Field


class RouteRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    user_profile: dict[str, Any] = Field(default_factory=dict)
    volley_msg_left: int = 0
    session_id: str | None = None
    trace_id: str | None = None


class RouteResponse(BaseModel):
    next_agent: str
    volley_msg_left: int
    routing_reason: str | None = None
    needs_clarification: bool = False
    safety_flags: list[str] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    prompt_version: str = "head-coach-routing-v1"
