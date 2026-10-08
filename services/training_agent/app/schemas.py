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


class TrainingProfileRequest(UserRequest):
    fitness_goal: str | None = Field(default=None, min_length=1, max_length=255)
    fitness_level: str | None = Field(default=None, min_length=1, max_length=50)


class TrainingPreferencesRequest(UserRequest):
    equipment: list[str] = Field(default_factory=list, max_length=30)
    training_days_per_week: int | None = Field(default=None, ge=1, le=7)
    session_duration_minutes: int | None = Field(default=None, ge=10, le=300)
    preferences: dict[str, Any] = Field(default_factory=dict)


class ExerciseSearchRequest(UserRequest):
    query: str = Field(min_length=1, max_length=128)


class ExerciseLookupRequest(ExerciseSearchRequest):
    pass


class ProgramGenerateRequest(UserRequest):
    recovery_status: RecoveryStatus = "no_assessment"


class ProgramListRequest(UserRequest):
    pass


class WorkoutLogRequest(UserRequest):
    occurred_at: datetime
    description: str = Field(min_length=1, max_length=4000)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    session_rpe: float | None = Field(default=None, ge=1, le=10)
    notes: str | None = Field(default=None, max_length=4000)
    exercise_performance: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


class ProgressRequest(UserRequest):
    days: int = Field(default=28, ge=7, le=365)


class WorkoutListRequest(ProgressRequest):
    limit: int = Field(default=50, ge=1, le=100)


class AdaptRequest(ProgramGenerateRequest):
    reason: str = Field(min_length=1, max_length=1000)


class DailyWorkoutRequest(UserRequest):
    date: date
    refresh: bool = False
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
