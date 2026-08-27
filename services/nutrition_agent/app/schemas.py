"""Request and response contracts for the Nutrition Agent."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


NutritionStatus = Literal["green", "amber", "red", "escalate"]
DietaryPreference = Literal["omnivore", "vegetarian", "vegan", "pescatarian", "other"]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very_active"]
MealType = Literal["breakfast", "lunch", "dinner", "snack"]
Gender = Literal["male", "female", "other"]


class NutritionProfileCreate(BaseModel):
    """Create or update nutrition profile."""

    user_id: int = Field(gt=0)
    dietary_preference: DietaryPreference = "omnivore"
    dietary_restrictions: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    meals_per_day: int = Field(default=3, ge=1, le=10)
    target_calories: int | None = Field(default=None, gt=0)
    activity_level: ActivityLevel = "moderate"
    age: int | None = Field(default=None, ge=1, le=120)
    gender: Gender | None = None
    weight_kg: float | None = Field(default=None, gt=0, le=300)
    height_cm: float | None = Field(default=None, gt=0, le=250)


class MealLogCreate(BaseModel):
    """Log a meal."""

    user_id: int = Field(gt=0)
    meal_type: MealType
    description: str = Field(min_length=1, max_length=1000)
    calories: int | None = Field(default=None, gt=0)
    protein_g: float | None = Field(default=None, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)


class NutritionEvaluateRequest(BaseModel):
    """Internal request from the orchestrator to the Nutrition Agent."""

    user_id: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=4000)
    profile: dict[str, Any] = Field(default_factory=dict)


class NutritionEvaluateResponse(BaseModel):
    """Response from nutrition assessment."""

    agent: Literal["nutrition"] = "nutrition"
    status: NutritionStatus
    score: int = Field(ge=0)
    message: str
    reasoning: str
    recommendations: list[str]
    tool_trace: list[str]
    tdee: int | None = None
    macro_targets: dict[str, Any] | None = None
    created_at: datetime


class MealLogResponse(BaseModel):
    """Response after logging a meal."""

    id: int
    user_id: int
    meal_type: str
    description: str
    calories: int | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    logged_at: datetime


class NutritionProfileResponse(BaseModel):
    """Nutrition profile response."""

    user_id: int
    dietary_preference: str
    dietary_restrictions: list[str]
    allergies: list[str]
    meals_per_day: int
    target_calories: int | None
    activity_level: str
    age: int | None
    gender: str | None
    weight_kg: float | None
    height_cm: float | None
    created_at: datetime
    updated_at: datetime


class NutritionHistoryResponse(BaseModel):
    """7-day nutrition history."""

    user_id: int
    meal_logs_last_7_days: int
    average_calories: float | None
    average_protein_g: float | None
    average_carbs_g: float | None
    average_fat_g: float | None
    adherence_percentage: float | None


class TDEEResponse(BaseModel):
    """TDEE calculation response."""

    tdee: int
    bmr: int
    activity_multiplier: float
    formula: str


class MacroTargetsResponse(BaseModel):
    """Macro target calculation response."""

    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    protein_percentage: float
    carbs_percentage: float
    fat_percentage: float


class FoodSearchResponse(BaseModel):
    """Food search result."""

    fdc_id: int
    name: str
    brand: str | None
    serving_size_g: int
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    category: str | None


class MealPlanResponse(BaseModel):
    """Meal plan response."""

    meals: dict[str, Any]
    total_calories: int
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
