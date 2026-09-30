"""Public, user-scoped contracts for the Daily Agent Command Center."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class DashboardDomainError(BaseModel):
    domain: Literal["nutrition", "recovery"]
    message: str


class TrainingDashboardSnapshot(BaseModel):
    status: Literal["unavailable"] = "unavailable"
    message: str
    last_activity_at: datetime | None = None


class TrainingWorkoutResponse(BaseModel):
    status: Literal["ready", "recovery_adjusted", "unavailable"]
    title: str
    workout_text: str
    recovery_note: str | None = None
    recovery_status: Literal[
        "green", "amber", "red", "escalate", "no_assessment", "unavailable"
    ]
    generated_at: datetime
    reused: bool = False


class NutritionTrendPoint(BaseModel):
    date: date
    calorie_adherence_pct: float | None = None
    protein_adherence_pct: float | None = None
    meal_count: int = 0


class NutritionDashboardSnapshot(BaseModel):
    status: Literal["available", "no_target", "unavailable"]
    message: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    meal_count: int | None = None
    calorie_target_kcal: float | None = None
    protein_target_g: float | None = None
    remaining_calories: float | None = None
    remaining_protein_g: float | None = None
    calorie_adherence_pct: float | None = None
    protein_adherence_pct: float | None = None
    trend: list[NutritionTrendPoint] = Field(default_factory=list)


class RecoveryTrendPoint(BaseModel):
    date: date
    sleep_duration_minutes: int | None = None
    sleep_quality: int | None = None
    assessment_status: Literal["green", "amber", "red", "escalate"] | None = None
    assessment_score: int | None = None


class RecoveryDashboardSnapshot(BaseModel):
    status: Literal["green", "amber", "red", "escalate", "no_assessment", "unavailable"]
    message: str | None = None
    assessment_score: int | None = None
    assessment_created_at: datetime | None = None
    sleep_duration_minutes: int | None = None
    sleep_quality: int | None = None
    sleep_logged_at: datetime | None = None
    energy: int | None = None
    soreness: int | None = None
    stress: int | None = None
    check_in_created_at: datetime | None = None
    trend: list[RecoveryTrendPoint] = Field(default_factory=list)


class DashboardAction(BaseModel):
    id: str
    priority: int = Field(ge=1)
    severity: Literal["critical", "warning", "info"]
    title: str
    description: str
    route: Literal["/chat", "/nutrition", "/recovery-table"]


class DailyCommandCenterResponse(BaseModel):
    generated_at: datetime
    dashboard_date: date
    training: TrainingDashboardSnapshot
    nutrition: NutritionDashboardSnapshot
    recovery: RecoveryDashboardSnapshot
    actions: list[DashboardAction] = Field(default_factory=list, max_length=3)
    errors: list[DashboardDomainError] = Field(default_factory=list)
