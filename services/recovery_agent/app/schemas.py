"""Request and response contracts for the Recovery Agent."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


RecoveryStatus = Literal["green", "amber", "red", "escalate"]


class SleepLogCreate(BaseModel):
    user_id: int = Field(gt=0)
    duration_minutes: int = Field(ge=0, le=1440)
    quality: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=1000)


class RecoveryCheckInCreate(BaseModel):
    user_id: int = Field(gt=0)
    energy: int = Field(ge=1, le=10)
    soreness: int = Field(ge=1, le=10)
    stress: int = Field(ge=1, le=10)
    notes: str | None = Field(default=None, max_length=1000)


class RecoveryEvaluateRequest(BaseModel):
    """Internal request from the orchestrator to the Recovery Agent."""

    user_id: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=4000)
    profile: dict[str, Any] = Field(default_factory=dict)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    sleep_quality: int | None = Field(default=None, ge=1, le=5)
    energy: int | None = Field(default=None, ge=1, le=10)
    soreness: int | None = Field(default=None, ge=1, le=10)
    stress: int | None = Field(default=None, ge=1, le=10)


class RecoveryEvaluateResponse(BaseModel):
    agent: Literal["recovery"] = "recovery"
    status: RecoveryStatus
    score: int = Field(ge=0)
    message: str
    reasoning: str
    recommendations: list[str]
    tool_trace: list[str]
    created_at: datetime


class SleepLogResponse(BaseModel):
    id: int
    user_id: int
    duration_minutes: int
    quality: int
    notes: str | None
    created_at: datetime


class RecoveryHistoryResponse(BaseModel):
    user_id: int
    sleep_logs_last_7_days: int
    average_sleep_minutes: float | None
    average_sleep_quality: float | None
    check_ins_last_7_days: int
    workouts_last_7_days: int
