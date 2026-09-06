"""Strict public schemas for Nutrition API proxy responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from services.nutrition_agent.app.schemas import (
    MealLogCreate,
    MealPlanRequest,
    NutritionProfileUpsert,
    TargetCalculateRequest,
    TargetSaveRequest,
)


class NutritionProfileWriteRequest(NutritionProfileUpsert):
    """Strict public profile replacement payload."""


class MealLogWriteRequest(MealLogCreate):
    """Strict public meal-log create or full-replacement payload."""


class TargetCalculatePublicRequest(TargetCalculateRequest):
    """Strict public target-calculation payload."""


class TargetSavePublicRequest(TargetSaveRequest):
    """Strict public immutable target-save payload."""


class MealPlanPublicRequest(MealPlanRequest):
    """Strict public meal-plan generation payload."""


class FoodResponse(BaseModel):
    """A normalized shared food-reference record."""

    model_config = ConfigDict(extra="forbid")

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


class FoodSearchResponse(BaseModel):
    """Cache-first food search metadata and records."""

    model_config = ConfigDict(extra="forbid")

    items: list[FoodResponse]
    source: Literal["cache", "cache_and_usda", "cache_only"]
    upstream_status: Literal["not_requested", "fresh", "unavailable", "circuit_open"]
    stale: bool = False
