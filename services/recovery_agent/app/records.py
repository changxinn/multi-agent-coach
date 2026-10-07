from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RecoveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0)


class SleepInput(RecoveryInput):
    duration_minutes: int = Field(ge=0, le=1440)
    quality: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=1000)


class CheckInInput(RecoveryInput):
    energy: int = Field(ge=1, le=10)
    soreness: int = Field(ge=1, le=10)
    stress: int = Field(ge=1, le=10)
    notes: str | None = Field(default=None, max_length=1000)


class AssessmentInput(RecoveryInput):
    status: Literal["green", "amber", "red", "escalate"]
    score: int = Field(ge=0)
    response: dict[str, Any]
    tool_trace: list[str]
