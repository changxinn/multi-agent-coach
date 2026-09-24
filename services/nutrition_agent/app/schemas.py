"""Authenticated private Nutrition Agent contracts."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyNutritionRequest(StrictModel):
    pass


class TargetCalculationRequest(StrictModel):
    sex: Literal["female", "male"]
    age: int = Field(gt=0)
    weight_kg: Decimal = Field(gt=0)
    height_cm: Decimal = Field(gt=0)
    activity_level: Literal[
        "sedentary", "light", "moderate", "very_active", "extra_active"
    ]
    goal: Literal["maintenance", "fat_loss", "muscle_gain", "performance"]


class TargetCalculationResponse(BaseModel):
    bmr_kcal: int
    tdee_kcal: int
    calorie_target_kcal: int
    protein_target_g: Decimal
    carbohydrate_target_g: Decimal
    fat_target_g: Decimal
    fiber_target_g: Decimal
    calculation_method: str


class UserRequest(StrictModel):
    user_id: int = Field(gt=0)


class ProfileRequest(UserRequest):
    values: dict[str, Any]


class TargetsRequest(UserRequest):
    confirm_apply: bool = False
    profile: TargetCalculationRequest


class FoodSearchRequest(UserRequest):
    query: str = Field(min_length=2, max_length=200)


class FoodDetailRequest(UserRequest):
    food_id: str = Field(min_length=1, max_length=64)


class FoodCatalogueRequest(UserRequest):
    pass


class MealItem(StrictModel):
    food_name: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=32)
    grams: Decimal | None = Field(default=None, gt=0)
    calories: Decimal = Field(ge=0)
    protein_g: Decimal = Field(default=Decimal(0), ge=0)
    carbohydrate_g: Decimal = Field(default=Decimal(0), ge=0)
    fat_g: Decimal = Field(default=Decimal(0), ge=0)
    fiber_g: Decimal = Field(default=Decimal(0), ge=0)
    source: Literal["usda", "manual_estimate", "meal_plan"] = "manual_estimate"
    food_cache_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def manual_estimates_include_macros(self) -> "MealItem":
        """Manual entries must contain deliberate nutrition values, including zeroes."""
        required = {"calories", "protein_g", "carbohydrate_g", "fat_g"}
        if self.source == "manual_estimate" and not required.issubset(
            self.model_fields_set
        ):
            missing = ", ".join(sorted(required - self.model_fields_set))
            raise ValueError(f"Manual estimates require explicit values for: {missing}")
        return self


class MealRequest(UserRequest):
    eaten_at: datetime
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    notes: str | None = Field(default=None, max_length=2000)
    items: list[MealItem] = Field(min_length=1)


class ReplaceMealRequest(MealRequest):
    meal_id: int = Field(gt=0)


class MealIdRequest(UserRequest):
    meal_id: int = Field(gt=0)


class DateRequest(UserRequest):
    date: date


class AdherenceRequest(UserRequest):
    from_date: date
    to_date: date


class PlannedMealInput(StrictModel):
    planned_date: date
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    calorie_target_kcal: Decimal = Field(ge=0)
    protein_target_g: Decimal = Field(ge=0)
    carbohydrate_target_g: Decimal = Field(ge=0)
    fat_target_g: Decimal = Field(ge=0)
    fiber_target_g: Decimal = Field(ge=0)
    items: list[MealItem] = Field(min_length=1)


class MealPlanCreateRequest(UserRequest):
    """Validated persistence contract for a generated, user-confirmed meal plan."""

    target_snapshot_id: int = Field(gt=0)
    profile: dict[str, Any] = Field(default_factory=dict)
    start_date: date
    end_date: date
    generated_plan: dict[str, Any] = Field(default_factory=dict)
    safety_warnings: list[str] = Field(default_factory=list)
    planned_meals: list[PlannedMealInput] = Field(min_length=1)

    @model_validator(mode="after")
    def dates_and_meals_are_within_the_plan(self) -> "MealPlanCreateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.end_date - self.start_date > timedelta(days=30):
            raise ValueError("Meal plans cannot span more than 31 days")
        if any(
            meal.planned_date < self.start_date or meal.planned_date > self.end_date
            for meal in self.planned_meals
        ):
            raise ValueError("Every planned meal must fall within the plan date range")
        return self


class MealPlanGenerateRequest(UserRequest):
    """User-selected scope for a deterministic, server-generated draft."""

    start_date: date
    profile: dict[str, Any] = Field(default_factory=dict)
    end_date: date
    meal_types: list[Literal["breakfast", "lunch", "dinner", "snack"]] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def dates_and_meal_types_are_valid(self) -> "MealPlanGenerateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.end_date - self.start_date > timedelta(days=30):
            raise ValueError("Meal plans cannot span more than 31 days")
        if len(set(self.meal_types)) != len(self.meal_types):
            raise ValueError("Meal types must be unique")
        return self


class MealPlanIdRequest(UserRequest):
    meal_plan_id: int = Field(gt=0)


class MealPlanConfirmRequest(MealPlanIdRequest):
    """Current main-application profile for confirmation-time safety checks."""

    profile: dict[str, Any] = Field(default_factory=dict)


class ConversationMessage(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)
    name: str | None = Field(default=None, max_length=200)


class ChatRequest(UserRequest):
    """Full gateway transcript for a conversational Nutrition Agent response."""

    messages: list[ConversationMessage] = Field(min_length=1, max_length=200)
    user_profile: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
