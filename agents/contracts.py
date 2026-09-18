"""Shared Pydantic contracts for Head Coach routing and specialist results."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class SpecialistId(StrEnum):
    TRAINING = "training_planner"
    NUTRITION = "nutrition_advisor"
    RECOVERY = "recovery_coach"


VALID_SPECIALISTS: frozenset[str] = frozenset(member.value for member in SpecialistId)


class ToolEvent(BaseModel):
    tool: str
    status: str
    detail: str | None = None


class AgentResult(BaseModel):
    agent: str
    answer: str
    recommendations: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    tool_events: list[ToolEvent] = Field(default_factory=list)
    explanation: str = ""


class RoutingDecision(BaseModel):
    agents: list[SpecialistId] = Field(default_factory=list)
    reason: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    needs_clarification: bool = False
    clarification_prompt: str | None = None


class SafetyDecision(BaseModel):
    allowed: bool = True
    escalate: bool = False
    flags: list[str] = Field(default_factory=list)
    action: str = "proceed"
    message: str | None = None


class TraceEvent(BaseModel):
    trace_id: str
    session_id: str | None = None
    agent: str | None = None
    event_type: str
    detail: dict[str, Any] = Field(default_factory=dict)
    prompt_version: str = "v1"
    model: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def new_trace_id() -> str:
    return str(uuid4())
