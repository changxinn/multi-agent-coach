"""Application services for nutrition profiles, targets, and meals."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.nutrition_repo import NutritionRepository
from app.services.food_data import FoodDataProviderError, UsdaFoodDataCentralProvider
from app.services.nutrition_calculator import calculate_targets


class NutritionNotFoundError(Exception):
    """Raised when a user-owned nutrition resource does not exist."""


class NutritionProfileIncompleteError(Exception):
    """Raised when target calculation prerequisites have not been saved."""


class NutritionFoodDataError(Exception):
    """Raised when food information cannot be safely obtained."""


class NutritionService:
    def __init__(
        self, db: AsyncSession, food_provider: UsdaFoodDataCentralProvider | None = None
    ):
        self.repo = NutritionRepository(db)
        self.food_provider = food_provider

    async def get_profile(self, user_id: int) -> dict[str, Any]:
        profile = await self.repo.get_profile(user_id)
        if profile is None:
            raise NutritionNotFoundError("Nutrition profile not found")
        return profile

    async def update_profile(
        self, user_id: int, values: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.repo.upsert_profile(user_id, values)

    async def calculate_targets(
        self, user_id: int, confirm_apply: bool
    ) -> dict[str, Any]:
        profile = await self.repo.get_profile_with_measurements(user_id)
        if profile is None:
            raise NutritionProfileIncompleteError(
                "Save a nutrition profile before calculating targets"
            )
        missing = [
            key for key in ("age", "weight_kg", "height_cm") if profile[key] is None
        ]
        if missing:
            raise NutritionProfileIncompleteError(
                f"Missing required fitness profile data: {', '.join(missing)}"
            )
        targets = calculate_targets(
            sex=profile["sex_for_energy_equation"],
            age=profile["age"],
            weight_kg=Decimal(profile["weight_kg"]),
            height_cm=Decimal(profile["height_cm"]),
            activity_level=profile["activity_level"],
            goal=profile["nutrition_goal"],
        )
        inputs = {
            key: str(profile[key])
            for key in (
                "sex_for_energy_equation",
                "activity_level",
                "nutrition_goal",
                "age",
                "weight_kg",
                "height_cm",
            )
        }
        preview = {**targets.__dict__, "calculation_inputs": inputs, "applied": False}
        if not confirm_apply:
            return preview
        today = datetime.now(UTC).date()
        values = {
            "bmr": targets.bmr_kcal,
            "tdee": targets.tdee_kcal,
            "calories": targets.calorie_target_kcal,
            "protein": targets.protein_target_g,
            "carbohydrates": targets.carbohydrate_target_g,
            "fat": targets.fat_target_g,
            "fiber": targets.fiber_target_g,
            "method": targets.calculation_method,
            "inputs": json.dumps(inputs),
        }
        active = await self.repo.lock_open_target(user_id)
        if active and active["effective_from"] == today:
            return {
                **await self.repo.update_target(active["id"], values),
                "applied": True,
            }
        if active:
            await self.repo.close_target(active["id"], today - timedelta(days=1))
        return {
            **await self.repo.create_target(user_id, today, values),
            "applied": True,
        }

    async def get_active_target(self, user_id: int) -> dict[str, Any]:
        target = await self.repo.get_active_target(user_id)
        if target is None:
            raise NutritionNotFoundError("No active nutrition targets")
        return target

    async def create_meal(self, user_id: int, payload: Any) -> dict[str, Any]:
        meal = payload.model_dump(exclude={"items", "meal_id"})
        items = [item.model_dump() for item in payload.items]
        record = await self.repo.create_meal(user_id, meal, items)
        return {
            **record,
            "items": [item.model_dump(mode="json") for item in payload.items],
        }

    async def list_meals(self, user_id: int, for_date: date) -> list[dict[str, Any]]:
        return await self.repo.list_meals(user_id, for_date)

    async def replace_meal(
        self, user_id: int, meal_id: int, payload: Any
    ) -> dict[str, Any]:
        meal = payload.model_dump(exclude={"items", "meal_id"})
        record = await self.repo.replace_meal(
            user_id, meal_id, meal, [item.model_dump() for item in payload.items]
        )
        if record is None:
            raise NutritionNotFoundError("Meal not found")
        return {
            **record,
            "items": [item.model_dump(mode="json") for item in payload.items],
        }

    async def delete_meal(self, user_id: int, meal_id: int) -> None:
        if not await self.repo.delete_meal(user_id, meal_id):
            raise NutritionNotFoundError("Meal not found")

    async def get_daily_summary(self, user_id: int, for_date: date) -> dict[str, Any]:
        totals = await self.repo.get_daily_totals(user_id, for_date)
        target = await self.repo.get_target_for_date(user_id, for_date)
        values = self._summary_values(totals, target)
        summary = await self.repo.upsert_daily_summary(user_id, for_date, values)
        return {
            "date": for_date,
            **summary,
            "target": target,
            "remaining": self._remaining(totals, target),
        }

    async def search_foods(self, query: str) -> list[dict[str, Any]]:
        provider = self._food_provider()
        try:
            foods = await provider.search_foods(query)
        except FoodDataProviderError as error:
            raise NutritionFoodDataError(str(error)) from error
        return [food.__dict__ for food in foods]

    async def get_food(self, provider_food_id: str) -> dict[str, Any]:
        cached = await self.repo.get_cached_food("usda", provider_food_id)
        if cached:
            return cached
        provider = self._food_provider()
        try:
            food = await provider.get_food_details(provider_food_id)
        except FoodDataProviderError as error:
            raise NutritionFoodDataError(str(error)) from error
        return await self.repo.cache_food(food.__dict__)

    async def get_adherence(
        self, user_id: int, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        summaries = []
        current = start_date
        while current <= end_date:
            summaries.append(await self.get_daily_summary(user_id, current))
            current += timedelta(days=1)
        return summaries

    def _food_provider(self) -> UsdaFoodDataCentralProvider:
        if self.food_provider is None:
            from app.config import get_settings

            self.food_provider = UsdaFoodDataCentralProvider(
                get_settings().USDA_FDC_API_KEY
            )
        return self.food_provider

    @staticmethod
    def _percentage(actual: Any, target: Any) -> Decimal | None:
        if not target:
            return None
        return (Decimal(str(actual)) / Decimal(str(target)) * Decimal(100)).quantize(
            Decimal("0.01")
        )

    def _summary_values(
        self, totals: dict[str, Any], target: dict[str, Any] | None
    ) -> dict[str, Any]:
        return {
            "target_snapshot_id": target["id"] if target else None,
            **totals,
            "calorie_adherence_pct": self._percentage(
                totals["calories"], target["calorie_target_kcal"] if target else None
            ),
            "protein_adherence_pct": self._percentage(
                totals["protein_g"], target["protein_target_g"] if target else None
            ),
            "plan_adherence_pct": None,
        }

    @staticmethod
    def _remaining(
        totals: dict[str, Any], target: dict[str, Any] | None
    ) -> dict[str, Decimal | None]:
        if target is None:
            return {
                "calories": None,
                "protein_g": None,
                "carbohydrate_g": None,
                "fat_g": None,
            }
        return {
            "calories": Decimal(str(target["calorie_target_kcal"]))
            - Decimal(str(totals["calories"])),
            "protein_g": Decimal(str(target["protein_target_g"]))
            - Decimal(str(totals["protein_g"])),
            "carbohydrate_g": Decimal(str(target["carbohydrate_target_g"]))
            - Decimal(str(totals["carbohydrate_g"])),
            "fat_g": Decimal(str(target["fat_target_g"]))
            - Decimal(str(totals["fat_g"])),
        }
