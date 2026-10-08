from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictTrainingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyTrainingRequest(StrictTrainingModel):
    pass


class TrainingPreferencesInput(StrictTrainingModel):
    equipment: list[str] = Field(default_factory=list, max_length=30)
    training_days_per_week: int | None = Field(default=None, ge=1, le=7)
    session_duration_minutes: int | None = Field(default=None, ge=10, le=300)
    preferences: dict[str, Any] = Field(default_factory=dict)


class ExerciseSearchInput(StrictTrainingModel):
    query: str = Field(min_length=1, max_length=128)


class ProgramAdaptInput(StrictTrainingModel):
    reason: str = Field(min_length=1, max_length=1000)


class WorkoutSetInput(StrictTrainingModel):
    repetitions: int | None = Field(default=None, ge=0, le=1000)
    weight_kg: float | None = Field(default=None, ge=0, le=1000)
    rpe: float | None = Field(default=None, ge=1, le=10)
    completed: bool = True


class ExercisePerformanceInput(StrictTrainingModel):
    exercise_name: str = Field(min_length=1, max_length=255)
    sets: list[WorkoutSetInput] = Field(default_factory=list, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


class WorkoutLogInput(StrictTrainingModel):
    occurred_at: datetime
    description: str = Field(min_length=1, max_length=4000)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    session_rpe: float | None = Field(default=None, ge=1, le=10)
    notes: str | None = Field(default=None, max_length=4000)
    exercise_performance: list[ExercisePerformanceInput] = Field(
        default_factory=list, max_length=100
    )


class WorkoutListInput(StrictTrainingModel):
    days: int = Field(default=28, ge=1, le=365)
    limit: int = Field(default=50, ge=1, le=100)


class ProgressInput(StrictTrainingModel):
    days: int = Field(default=28, ge=7, le=365)
