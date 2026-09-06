"""Canonical private request and response contracts for Nutrition Agent."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NutritionStatus = Literal["green", "amber", "red", "escalate"]
DietaryPreference = Literal["omnivore", "vegetarian", "vegan", "pescatarian", "other"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
MealType = Literal["breakfast", "lunch", "dinner", "snack"]
Gender = Literal["male", "female", "other"]
PregnancyStatus = Literal["unknown", "not_pregnant_or_breastfeeding", "pregnant", "breastfeeding", "pregnant_and_breastfeeding"]
MedicalCondition = Literal["diabetes", "uses_insulin_or_glucose_lowering_medication", "kidney_disease", "heart_disease", "hypertension", "eating_disorder_history"]
RiskFlag = Literal["under_18", "current_disordered_eating_behaviors", "chest_pain_or_breathing_difficulty", "fainting_or_severe_dizziness", "purging_or_laxative_use", "severe_food_restriction", "rapid_weight_loss_request", "other_medical_condition"]


def _normal_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Values must not be empty")
        key = normalized.casefold()
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SafetyContext(StrictModel):
    pregnancy_lactation_status: PregnancyStatus | None = None
    medical_conditions: list[MedicalCondition] = Field(default_factory=list, max_length=6)
    risk_flags: list[RiskFlag] = Field(default_factory=list)

    @field_validator("medical_conditions", "risk_flags")
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        # Context is request-scoped and only informs the ordered policy codes.
        # Collapse repeated valid enum values rather than rejecting an otherwise
        # safe request; source ordering is deliberately not retained downstream.
        return list(dict.fromkeys(values))


class SafetyFinding(StrictModel):
    code: str
    severity: Literal["escalate", "warning"]


class Escalation(StrictModel):
    message: str
    urgent: bool


class NutritionProfileUpsert(StrictModel):
    timezone: str = Field(min_length=1, max_length=64)
    dietary_preference: DietaryPreference = "omnivore"
    dietary_restrictions: list[str] = Field(default_factory=list, max_length=20)
    allergies: list[str] = Field(default_factory=list, max_length=20)
    meals_per_day: int = Field(default=3, ge=1, le=10)
    activity_level: ActivityLevel = "moderate"
    age: int | None = Field(default=None, ge=1, le=120)
    gender: Gender | None = None
    weight_kg: float | None = Field(default=None, gt=0, le=300)
    height_cm: float | None = Field(default=None, gt=0, le=250)

    @field_validator("dietary_restrictions", "allergies")
    @classmethod
    def normalize_restrictions(cls, values: list[str]) -> list[str]:
        if any(len(value.strip()) > 80 for value in values):
            raise ValueError("Values must be at most 80 characters")
        return _normal_strings(values)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        timezone = value.strip()
        if not timezone:
            raise ValueError("Timezone must not be empty")
        try:
            ZoneInfo(timezone)
        except (KeyError, ValueError) as error:
            raise ValueError("Timezone must be a valid IANA timezone") from error
        return timezone


class NutritionProfileResponse(NutritionProfileUpsert):
    user_id: int = Field(gt=0)
    created_at: datetime
    updated_at: datetime


class MealLogCreate(StrictModel):
    meal_type: MealType
    description: str = Field(min_length=1, max_length=1000)
    calories: int | None = Field(default=None, ge=1, le=10000)
    protein_g: float | None = Field(default=None, ge=0, le=2000)
    carbs_g: float | None = Field(default=None, ge=0, le=2000)
    fat_g: float | None = Field(default=None, ge=0, le=2000)
    logged_at: datetime | None = None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Description must not be empty")
        return value


class MealLogResponse(MealLogCreate):
    id: int
    user_id: int
    logged_at: datetime


class Pagination(StrictModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)


class PaginatedMealLogs(Pagination):
    items: list[MealLogResponse]
    total: int


class TargetInputs(StrictModel):
    age: int = Field(ge=1, le=120)
    gender: Gender
    weight_kg: float = Field(gt=0, le=300)
    height_cm: float = Field(gt=0, le=250)
    activity_level: ActivityLevel
    fitness_goal: Literal["weight_loss", "maintenance", "muscle_gain"]
    requested_weekly_loss_kg: float | None = Field(default=None, gt=0, le=5)
    safety_context: SafetyContext | None = None


class TargetCalculateRequest(StrictModel):
    inputs: TargetInputs


class TargetSaveRequest(TargetCalculateRequest):
    effective_from: date


class NutritionTargetResponse(StrictModel):
    id: int | None = None
    inputs: TargetInputs
    recommended_calories: int
    macro_targets: dict[str, float | int]
    policy_version: str
    effective_from: date | None = None
    effective_to: date | None = None
    safety_findings: list[SafetyFinding]
    escalation: Escalation | None = None


class NutritionEvaluateRequest(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    safety_context: SafetyContext | None = None
    profile: NutritionProfileUpsert | None = None

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must not be empty")
        return value


class NutritionEvaluateResponse(StrictModel):
    agent: Literal["nutrition"] = "nutrition"
    status: NutritionStatus
    score: int = Field(ge=0, le=10)
    message: str
    recommendations: list[str] = Field(max_length=10)
    tdee: int | None = None
    macro_targets: dict[str, float | int] | None = None
    safety_findings: list[SafetyFinding] = Field(default_factory=list)
    escalation: Escalation | None = None
    policy_version: str = "nutrition-safety-v1"
    created_at: datetime


class AssessmentHistoryItem(NutritionEvaluateResponse):
    id: int


class PaginatedAssessments(Pagination):
    items: list[AssessmentHistoryItem]
    total: int


class FoodResponse(StrictModel):
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
    source: str = "cache"
    cache_hit: bool = True
    last_updated: datetime | None = None


class FoodSearchResponse(StrictModel):
    items: list[FoodResponse]
    source: Literal["cache", "cache_and_usda", "cache_only"]
    upstream_status: Literal["not_requested", "fresh", "unavailable", "circuit_open"]
    stale: bool = False


class MealPlanRequest(StrictModel):
    target_inputs: TargetInputs | None = None
    use_current_target: bool = False
    start_date: date | None = None
    days: int = Field(ge=1, le=7)
    excluded_foods: list[str] = Field(default_factory=list, max_length=20)
    safety_context: SafetyContext | None = None

    @model_validator(mode="after")
    def require_target_source(self) -> MealPlanRequest:
        if (self.target_inputs is None) == (self.use_current_target is False):
            raise ValueError("Provide target_inputs or set use_current_target to true")
        return self

    @field_validator("excluded_foods")
    @classmethod
    def normalize_exclusions(cls, values: list[str]) -> list[str]:
        if any(len(value.strip()) > 80 for value in values):
            raise ValueError("Values must be at most 80 characters")
        return _normal_strings(values)


class MealPlanResponse(StrictModel):
    days: list[dict]
    total_calories: int
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    safety_findings: list[SafetyFinding]
    policy_version: str
    disclaimer: str


class DailyNutritionHistory(StrictModel):
    start_date: date
    end_date: date
    timezone: str
    days_with_logs: int
    days: list[dict]
    average_daily_calories: float | None = None
    average_daily_protein_g: float | None = None
    average_daily_carbs_g: float | None = None
    average_daily_fat_g: float | None = None
    calorie_adherence_percentage: float | None = None


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except Exception as error:
        raise ValueError("Invalid IANA timezone") from error
    return value