from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RecoveryStatus = Literal[
    "green", "amber", "red", "escalate", "no_assessment", "unavailable"
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserRequest(StrictModel):
    user_id: int = Field(gt=0)


class ExerciseSearchRequest(UserRequest):
    query: str = Field(min_length=1, max_length=128)


class ExerciseLookupRequest(ExerciseSearchRequest):
    pass


class ProgramGenerateRequest(UserRequest):
    profile: dict[str, Any] = Field(default_factory=dict)
    recovery_status: RecoveryStatus = "no_assessment"
    workout_history_summary: dict[str, Any] = Field(default_factory=dict)


class ProgramListRequest(UserRequest):
    pass


class WorkoutLogRequest(UserRequest):
    occurred_at: datetime
    description: str = Field(min_length=1, max_length=4000)
    rpe: float | None = Field(default=None, ge=1, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProgressRequest(UserRequest):
    days: int = Field(default=28, ge=7, le=365)


class AdaptRequest(ProgramGenerateRequest):
    reason: str = Field(min_length=1, max_length=1000)


class DailyWorkoutRequest(UserRequest):
    date: date
    refresh: bool = False
    profile: dict[str, Any] = Field(default_factory=dict)
    recovery_status: RecoveryStatus = "no_assessment"


class ConversationMessage(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)
    name: str | None = Field(default=None, max_length=200)


class ChatRequest(UserRequest):
    messages: list[ConversationMessage] = Field(min_length=1, max_length=200)
    user_profile: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(StrictModel):
    message: str
    tool_trace: list[str] = Field(default_factory=list)
