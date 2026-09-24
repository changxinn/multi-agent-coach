from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NutritionProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sex_for_energy_equation: Literal["female", "male"]
    activity_level: Literal[
        "sedentary", "light", "moderate", "very_active", "extra_active"
    ]
    nutrition_goal: Literal["maintenance", "fat_loss", "muscle_gain", "performance"]
    allergies: list[str] = Field(default_factory=list)


class MealItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
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
    def manual_estimates_include_macros(self) -> "MealItemInput":
        """Manual entries must contain deliberate nutrition values, including zeroes."""
        required = {"calories", "protein_g", "carbohydrate_g", "fat_g"}
        if self.source == "manual_estimate" and not required.issubset(
            self.model_fields_set
        ):
            missing = ", ".join(sorted(required - self.model_fields_set))
            raise ValueError(f"Manual estimates require explicit values for: {missing}")
        return self


class MealInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eaten_at: datetime
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    notes: str | None = Field(default=None, max_length=2000)
    items: list[MealItemInput] = Field(min_length=1)


class EmptyNutritionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FoodSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=200)


class FoodDetailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    food_id: str = Field(min_length=1, max_length=64)


class FoodCatalogueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NutritionDateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date


class AdherenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_date: date
    to_date: date


class MealIdRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_id: int = Field(gt=0)


class ReplaceMealRequest(MealInput):
    meal_id: int = Field(gt=0)


class TargetCalculationRequest(BaseModel):
    """Targets are previewed unless the user explicitly confirms application."""

    model_config = ConfigDict(extra="forbid")
    confirm_apply: bool = False


class PlannedMealItemInput(MealItemInput):
    """A generated plan may only contain planned, not user-logged, food items."""

    source: Literal["meal_plan"] = "meal_plan"


class PlannedMealInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    planned_date: date
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    calorie_target_kcal: Decimal = Field(ge=0)
    protein_target_g: Decimal = Field(ge=0)
    carbohydrate_target_g: Decimal = Field(ge=0)
    fat_target_g: Decimal = Field(ge=0)
    fiber_target_g: Decimal = Field(ge=0)
    items: list[PlannedMealItemInput] = Field(min_length=1)
    safety_warnings: list[str] = Field(default_factory=list)


class MealPlanCreateInput(BaseModel):
    """Generated plan content saved for server-side safety review as a draft."""

    model_config = ConfigDict(extra="forbid")
    target_snapshot_id: int = Field(gt=0)
    start_date: date
    end_date: date
    generated_plan: dict[str, object] = Field(default_factory=dict)
    safety_warnings: list[str] = Field(default_factory=list)
    planned_meals: list[PlannedMealInput] = Field(min_length=1)

    @model_validator(mode="after")
    def dates_and_meals_are_valid(self) -> "MealPlanCreateInput":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.end_date - self.start_date > timedelta(days=30):
            raise ValueError("Meal plans cannot span more than 31 days")
        meal_keys = {(meal.planned_date, meal.meal_type) for meal in self.planned_meals}
        if len(meal_keys) != len(self.planned_meals):
            raise ValueError("A plan may contain only one meal of each type per date")
        if any(
            meal.planned_date < self.start_date or meal.planned_date > self.end_date
            for meal in self.planned_meals
        ):
            raise ValueError("Every planned meal must fall within the plan date range")
        return self


class MealPlanGenerateInput(BaseModel):
    """Scope selected by the user for a server-generated meal-plan draft."""

    model_config = ConfigDict(extra="forbid")
    start_date: date
    end_date: date
    meal_types: list[Literal["breakfast", "lunch", "dinner", "snack"]] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def dates_and_meal_types_are_valid(self) -> "MealPlanGenerateInput":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.end_date - self.start_date > timedelta(days=30):
            raise ValueError("Meal plans cannot span more than 31 days")
        if len(set(self.meal_types)) != len(self.meal_types):
            raise ValueError("Meal types must be unique")
        return self


class MealPlanIdRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_plan_id: int = Field(gt=0)
