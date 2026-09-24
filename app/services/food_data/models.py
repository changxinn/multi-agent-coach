"""Provider-neutral food data models."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class FoodSearchResult:
    provider: str
    provider_food_id: str
    description: str
    data_type: str | None = None


@dataclass(frozen=True)
class FoodDetails:
    provider: str
    provider_food_id: str
    description: str
    serving_size_g: Decimal | None
    serving_description: str | None
    calories_per_100g: Decimal | None
    protein_g_per_100g: Decimal | None
    carbohydrate_g_per_100g: Decimal | None
    fat_g_per_100g: Decimal | None
    fiber_g_per_100g: Decimal | None
    raw_response: dict[str, Any]
    allergen_data: dict[str, Any] | None = None
    allergen_status: str = "unknown"
