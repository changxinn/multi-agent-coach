from datetime import date, datetime
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
    dietary_preferences: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
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
    limit: int = Field(default=200, ge=1, le=500)


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
