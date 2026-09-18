"""Strict, POST-only contracts for direct Nutrition Management operations."""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from services.nutrition_agent.app.schemas import (
    ActivityLevel,
    DietaryPreference,
    Gender,
    MealType,
    TargetInputs,
)


class ManagementModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyRequest(ManagementModel):
    """Explicit empty payload required by POST-only read operations."""


class ResourceRequest(ManagementModel):
    id: int = Field(gt=0)


class PaginationRequest(ManagementModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10_000)


class ProfileWriteRequest(ManagementModel):
    timezone: str = "Asia/Singapore"
    dietary_preference: DietaryPreference = "omnivore"
    dietary_restrictions: list[str] = Field(default_factory=list, max_length=20)
    allergies: list[str] = Field(default_factory=list, max_length=20)
    meals_per_day: int = Field(default=3, ge=1, le=10)
    activity_level: ActivityLevel = "moderate"
    age: int | None = Field(default=None, ge=1, le=120)
    gender: Gender | None = None
    weight_kg: float | None = Field(default=None, gt=0, le=300)
    height_cm: float | None = Field(default=None, gt=0, le=250)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception as error:
            raise ValueError("Invalid IANA timezone") from error
        return value


class MealWriteRequest(ManagementModel):
    meal_type: MealType
    description: str = Field(min_length=1, max_length=1_000)
    calories: int | None = Field(default=None, ge=0, le=10_000)
    protein_g: float | None = Field(default=None, ge=0, le=2_000)
    carbs_g: float | None = Field(default=None, ge=0, le=2_000)
    fat_g: float | None = Field(default=None, ge=0, le=2_000)
    logged_at: datetime | None = None

    @model_validator(mode="after")
    def nutrient_present(self) -> MealWriteRequest:
        if all(value is None for value in (self.calories, self.protein_g, self.carbs_g, self.fat_g)):
            raise ValueError("At least one nutrient value is required")
        return self


class MealUpdateRequest(MealWriteRequest):
    id: int = Field(gt=0)


class DateRangeRequest(ManagementModel):
    start_date: Date
    end_date: Date
    timezone: str = "Asia/Singapore"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception as error:
            raise ValueError("Invalid IANA timezone") from error
        return value

    @model_validator(mode="after")
    def valid_range(self) -> DateRangeRequest:
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 30:
            raise ValueError("Date range must be between zero and 30 days")
        return self


class MealListRequest(PaginationRequest):
    start_date: Date | None = None
    end_date: Date | None = None
    timezone: str = "Asia/Singapore"

    @model_validator(mode="after")
    def complete_date_range(self) -> MealListRequest:
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be supplied together")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self


class FoodSearchRequest(ManagementModel):
    q: str = Field(min_length=1, max_length=100)
    limit: int = Field(default=20, ge=1, le=50)


class TargetCalculateRequest(ManagementModel):
    inputs: TargetInputs


class TargetSaveRequest(TargetCalculateRequest):
    effective_from: Date


class CurrentTargetRequest(ManagementModel):
    date: Date | None = None


class AssessmentListRequest(PaginationRequest):
    pass


class ProfileResponse(ProfileWriteRequest):
    user_id: int
    created_at: datetime
    updated_at: datetime


class MealResponse(MealWriteRequest):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class FoodResponse(ManagementModel):
    fdc_id: int
    name: str
    brand: str | None = None
    serving_size_g: int | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    category: str | None = None
    last_updated: datetime | None = None


class AssessmentResponse(ManagementModel):
    id: int
    status: Literal["green", "amber", "red", "escalate"]
    score: int
    tdee: int | None = None
    macro_targets: dict[str, float | int] | None = None
    message: str
    recommendations: list[str]
    safety_findings: list[dict[str, str]]
    policy_version: str
    created_at: datetime