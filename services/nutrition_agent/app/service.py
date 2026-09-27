"""Application services for nutrition profiles, targets, and meals."""

import hashlib
import json
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .calculator import calculate_targets
from .food_data import FoodDataProviderError, UsdaFoodDataCentralProvider
from .meal_plan_eligibility import is_eligible_for_meal_plan
from .meal_plan_generator import MealPlanGenerationError, MealPlanLLMGenerator
from .meal_plan_safety import assess_meal_plan_safety
from .repository import NutritionRepository
from .schemas import (
    MealPlanCreateRequest,
    MealPlanGenerateRequest,
    TargetCalculationRequest,
)

logger = logging.getLogger("uvicorn.error")


class NutritionNotFoundError(Exception):
    """Raised when a user-owned nutrition resource does not exist."""


class NutritionProfileIncompleteError(Exception):
    """Raised when target calculation prerequisites have not been saved."""


class NutritionFoodDataError(Exception):
    """Raised when food information cannot be safely obtained."""


class NutritionMealPlanSafetyError(Exception):
    """Raised when confirmed meal-plan content conflicts with a known allergy."""


class NutritionMealPlanTransitionError(Exception):
    """Raised when a meal plan cannot make the requested lifecycle transition."""


def _normalised_values(values: Any) -> set[str]:
    return {
        " ".join(str(value).casefold().replace("_", " ").split())
        for value in values or []
        if str(value).strip()
    }


def _allergen_values(value: Any) -> set[str]:
    if isinstance(value, str):
        return _normalised_values([value])
    if isinstance(value, dict):
        return set().union(*(_allergen_values(nested) for nested in value.values()))
    if isinstance(value, list):
        return set().union(*(_allergen_values(nested) for nested in value))
    return set()


def _food_is_safe_for_generation(
    food: dict[str, Any], metadata: dict[str, Any] | None, allergies: set[str]
) -> bool:
    if (
        not is_eligible_for_meal_plan(food)
        or not metadata
        or Decimal(food["calories_per_100g"]) <= 0
    ):
        return False
    allergen_status = metadata.get("allergen_status")
    if allergen_status == "unknown":
        return not allergies
    return bool(
        allergen_status == "known"
        and not (allergies & _allergen_values(metadata.get("allergen_data")))
    )


def _meal_targets(target: dict[str, Any], meal_count: int) -> dict[str, Decimal]:
    return {
        field: (Decimal(target[field]) / meal_count).quantize(Decimal("0.01"))
        for field in (
            "calorie_target_kcal",
            "protein_target_g",
            "carbohydrate_target_g",
            "fat_target_g",
            "fiber_target_g",
        )
    }


def _grams_for_calories(food: dict[str, Any], calories: Decimal) -> Decimal:
    return (calories * Decimal(100) / Decimal(food["calories_per_100g"])).quantize(
        Decimal("0.01")
    )


def _request_ranked_foods(
    foods: list[dict[str, Any]], request_id: str
) -> list[dict[str, Any]]:
    """Return a repeatable request-specific order without catalogue sort bias."""
    return sorted(
        foods,
        key=lambda food: hashlib.sha256(f"{request_id}:{food['id']}".encode()).digest(),
    )


def _planned_food_item(food: dict[str, Any], grams: Decimal) -> dict[str, Any]:
    multiplier = grams / Decimal(100)
    return {
        "food_name": food["description"],
        "quantity": grams,
        "unit": "g",
        "grams": grams,
        "calories": (Decimal(food["calories_per_100g"]) * multiplier).quantize(
            Decimal("0.01")
        ),
        "protein_g": (Decimal(food["protein_g_per_100g"]) * multiplier).quantize(
            Decimal("0.01")
        ),
        "carbohydrate_g": (
            Decimal(food["carbohydrate_g_per_100g"]) * multiplier
        ).quantize(Decimal("0.01")),
        "fat_g": (Decimal(food["fat_g_per_100g"]) * multiplier).quantize(
            Decimal("0.01")
        ),
        "fiber_g": (Decimal(food.get("fiber_g_per_100g") or 0) * multiplier).quantize(
            Decimal("0.01")
        ),
        "source": "meal_plan",
        "food_cache_id": food["id"],
    }


class NutritionService:
    def __init__(
        self,
        db: AsyncSession,
        food_provider: UsdaFoodDataCentralProvider | None = None,
        meal_plan_generator: MealPlanLLMGenerator | None = None,
    ):
        self.repo = NutritionRepository(db)
        self.food_provider = food_provider
        self.meal_plan_generator = meal_plan_generator

    async def idempotent(
        self,
        user_id: int,
        operation: str,
        key: str | None,
        request: dict[str, Any],
        action,
    ) -> dict[str, Any]:
        """Execute a mutation once and replay its stored response for the same request."""
        if not key:
            return await action()
        fingerprint = hashlib.sha256(
            json.dumps(
                request, sort_keys=True, default=str, separators=(",", ":")
            ).encode()
        ).hexdigest()
        existing = await self.repo.get_idempotent_response(user_id, operation, key)
        if existing:
            if existing["request_fingerprint"] != fingerprint:
                raise ValueError(
                    "Idempotency key was already used with a different request"
                )
            return existing["response"]
        response = await action()
        await self.repo.save_idempotent_response(
            user_id, operation, key, fingerprint, json.dumps(response, default=str)
        )
        return response

    async def create_meal_plan(
        self, user_id: int, payload: MealPlanCreateRequest
    ) -> dict[str, Any]:
        """Persist a safety-evaluated plan as a draft owned by the user."""
        target = await self.repo.get_target_snapshot(
            user_id, payload.target_snapshot_id
        )
        if target is None:
            raise NutritionNotFoundError("Nutrition target snapshot not found")
        planned_meals = [meal.model_dump() for meal in payload.planned_meals]
        food_cache_ids = {
            item["food_cache_id"]
            for meal in planned_meals
            for item in meal["items"]
            if item.get("food_cache_id") is not None
        }
        planned_meals, safety_warnings = assess_meal_plan_safety(
            planned_meals,
            payload.profile,
            await self.repo.get_food_safety_metadata(food_cache_ids),
        )
        if any(meal["safety_status"] == "blocked" for meal in planned_meals):
            raise NutritionMealPlanSafetyError(
                "Meal plan contains foods that conflict with confirmed allergies"
            )
        return await self.repo.create_meal_plan(
            user_id=user_id,
            target_snapshot_id=payload.target_snapshot_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            generated_plan=payload.generated_plan,
            safety_warnings=safety_warnings,
            planned_meals=planned_meals,
        )

    async def generate_meal_plan(
        self,
        user_id: int,
        payload: MealPlanGenerateRequest,
        *,
        request_id: str = "missing",
    ) -> dict[str, Any]:
        """Create an LLM-selected, server-materialized draft with deterministic fallback."""
        target = await self.repo.get_active_target(user_id)
        if target is None:
            raise NutritionProfileIncompleteError(
                "Active nutrition targets are required before generating a meal plan"
            )
        logger.info(
            "Meal-plan generation target loaded request_id=%s user_id=%d target_snapshot_id=%s",
            request_id,
            user_id,
            target["id"],
        )
        profile = payload.profile
        generated_meals = await self._try_generate_llm_meals(
            target, payload, request_id=request_id
        )
        if generated_meals is not None:
            try:
                planned_meals = await self._materialize_llm_meals(
                    generated_meals, target, payload
                )
                create_payload = MealPlanCreateRequest(
                    user_id=user_id,
                    target_snapshot_id=target["id"],
                    start_date=payload.start_date,
                    end_date=payload.end_date,
                    generated_plan={
                        "generator": "llm_cached_usda_tools_v1",
                        "target_snapshot_id": target["id"],
                        "meal_types": payload.meal_types,
                    },
                    planned_meals=planned_meals,
                    profile=profile,
                )
                logger.info(
                    "Meal-plan generation persisting LLM draft request_id=%s user_id=%d meal_count=%d",
                    request_id,
                    user_id,
                    len(planned_meals),
                )
                return await self.create_meal_plan(user_id, create_payload)
            except MealPlanGenerationError as error:
                logger.warning(
                    "Meal-plan generation LLM materialization failed; using deterministic fallback request_id=%s user_id=%d error_type=%s",
                    request_id,
                    user_id,
                    type(error).__name__,
                )
        foods = await self.repo.list_food_catalogue(500)
        safety_metadata = await self.repo.get_food_safety_metadata(
            {food["id"] for food in foods}
        )
        allergies = _normalised_values(profile.get("allergies"))
        safe_foods = [
            food
            for food in foods
            if _food_is_safe_for_generation(
                food, safety_metadata.get(food["id"]), allergies
            )
        ]
        if not safe_foods:
            raise NutritionProfileIncompleteError(
                "The local food catalogue has no safe foods with complete nutrition and compatible allergen data"
            )
        safe_foods = _request_ranked_foods(safe_foods, request_id)
        logger.info(
            "Meal-plan generation using deterministic fallback request_id=%s user_id=%d safe_food_count=%d",
            request_id,
            user_id,
            len(safe_foods),
        )

        meal_count = len(payload.meal_types)
        planned_meals: list[dict[str, Any]] = []
        day_count = (payload.end_date - payload.start_date).days + 1
        for day_offset in range(day_count):
            planned_date = payload.start_date + timedelta(days=day_offset)
            for meal_index, meal_type in enumerate(payload.meal_types):
                food = safe_foods[
                    (day_offset * meal_count + meal_index) % len(safe_foods)
                ]
                targets = _meal_targets(target, meal_count)
                grams = _grams_for_calories(food, targets["calorie_target_kcal"])
                planned_meals.append(
                    {
                        "planned_date": planned_date,
                        "meal_type": meal_type,
                        **targets,
                        "items": [_planned_food_item(food, grams)],
                    }
                )

        create_payload = MealPlanCreateRequest(
            user_id=user_id,
            target_snapshot_id=target["id"],
            start_date=payload.start_date,
            end_date=payload.end_date,
            generated_plan={
                "generator": "deterministic_catalogue_v1",
                "target_snapshot_id": target["id"],
                "meal_types": payload.meal_types,
                "catalogue_food_ids": [food["id"] for food in safe_foods],
            },
            planned_meals=planned_meals,
            profile=profile,
        )
        logger.info(
            "Meal-plan generation persisting deterministic draft request_id=%s user_id=%d meal_count=%d",
            request_id,
            user_id,
            len(planned_meals),
        )
        return await self.create_meal_plan(user_id, create_payload)

    async def _try_generate_llm_meals(
        self,
        target: dict[str, Any],
        payload: MealPlanGenerateRequest,
        *,
        request_id: str,
    ) -> list[dict[str, Any]] | None:
        """Use the LLM opportunistically; generation must never prevent a draft."""
        if self.meal_plan_generator is None:
            from .config import settings

            self.meal_plan_generator = MealPlanLLMGenerator(settings, self.repo)
        try:
            return await self.meal_plan_generator.generate(
                target=target,
                profile=payload.profile,
                start_date=payload.start_date,
                end_date=payload.end_date,
                meal_types=payload.meal_types,
                request_id=request_id,
            )
        except MealPlanGenerationError as error:
            logger.warning(
                "Meal-plan LLM generation unavailable; using deterministic fallback request_id=%s error_type=%s",
                request_id,
                type(error).__name__,
            )
            return None

    async def _materialize_llm_meals(
        self,
        generated_meals: list[dict[str, Any]],
        target: dict[str, Any],
        payload: MealPlanGenerateRequest,
    ) -> list[dict[str, Any]]:
        """Resolve selected IDs and calculate all plan nutrition from cached facts."""
        food_ids = {
            item["food_cache_id"] for meal in generated_meals for item in meal["items"]
        }
        foods = await self.repo.get_food_catalogue_by_ids(food_ids)
        if set(foods) != food_ids:
            raise MealPlanGenerationError(
                "LLM-selected food is not in the local catalogue"
            )
        metadata = await self.repo.get_food_safety_metadata(food_ids)
        allergies = _normalised_values(payload.profile.get("allergies"))
        if any(
            not _food_is_safe_for_generation(food, metadata.get(food_id), allergies)
            for food_id, food in foods.items()
        ):
            raise MealPlanGenerationError(
                "LLM-selected food is not safe for this profile"
            )
        targets = _meal_targets(target, len(payload.meal_types))
        return [
            {
                "planned_date": meal["planned_date"],
                "meal_type": meal["meal_type"],
                **targets,
                "items": [
                    _planned_food_item(
                        foods[item["food_cache_id"]], Decimal(str(item["grams"]))
                    )
                    for item in meal["items"]
                ],
            }
            for meal in generated_meals
        ]

    async def get_meal_plan(self, user_id: int, meal_plan_id: int) -> dict[str, Any]:
        plan = await self.repo.get_meal_plan(user_id, meal_plan_id)
        if plan is None:
            raise NutritionNotFoundError("Meal plan not found")
        return plan

    async def list_meal_plans(self, user_id: int) -> list[dict[str, Any]]:
        return await self.repo.list_meal_plans(user_id)

    async def confirm_meal_plan(
        self, user_id: int, meal_plan_id: int, *, profile: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        await self.repo.lock_user_meal_plans(user_id)
        plan = await self.get_meal_plan(user_id, meal_plan_id)
        if plan["status"] != "draft":
            raise NutritionMealPlanTransitionError(
                "Only draft meal plans can be confirmed"
            )
        planned_meals = plan["planned_meals"]
        food_cache_ids = {
            item["food_cache_id"]
            for meal in planned_meals
            for item in meal["items"]
            if item.get("food_cache_id") is not None
        }
        assessed_meals, safety_warnings = assess_meal_plan_safety(
            planned_meals,
            profile or {},
            await self.repo.get_food_safety_metadata(food_cache_ids),
        )
        if any(meal["safety_status"] == "blocked" for meal in assessed_meals):
            raise NutritionMealPlanSafetyError(
                "Meal plan contains foods that conflict with confirmed allergies"
            )
        confirmed = await self.repo.activate_draft_meal_plan(
            user_id,
            meal_plan_id,
            plan["start_date"],
            plan["end_date"],
            assessed_meals,
            safety_warnings,
        )
        if confirmed is None:
            raise NutritionMealPlanTransitionError(
                "Only draft meal plans can be confirmed"
            )
        return confirmed

    async def archive_meal_plan(
        self, user_id: int, meal_plan_id: int
    ) -> dict[str, Any]:
        await self.repo.lock_user_meal_plans(user_id)
        plan = await self.get_meal_plan(user_id, meal_plan_id)
        if plan["status"] not in {"draft", "active"}:
            raise NutritionMealPlanTransitionError(
                "Only draft or active meal plans can be archived"
            )
        archived = await self.repo.archive_meal_plan(user_id, meal_plan_id)
        if archived is None:
            raise NutritionMealPlanTransitionError(
                "Only draft or active meal plans can be archived"
            )
        return archived

    async def delete_meal_plan(
        self, user_id: int, meal_plan_id: int
    ) -> dict[str, bool]:
        """Permanently delete any plan owned by the user, regardless of lifecycle state."""
        if not await self.repo.delete_meal_plan(user_id, meal_plan_id):
            raise NutritionNotFoundError("Meal plan not found")
        return {"deleted": True}

    async def get_active_meal_plan(
        self, user_id: int, for_date: date
    ) -> dict[str, Any] | None:
        return await self.repo.get_active_meal_plan(user_id, for_date)

    async def get_nutrition_context(
        self, user_id: int, for_date: date
    ) -> dict[str, Any]:
        """Return only authoritative user-scoped target and plan context for a date."""
        return {
            "date": for_date,
            "target_snapshot": await self.repo.get_target_for_date(user_id, for_date),
            "meal_plan": await self.repo.get_active_meal_plan(user_id, for_date),
        }

    async def calculate_targets(
        self, user_id: int, confirm_apply: bool, profile: TargetCalculationRequest
    ) -> dict[str, Any]:
        targets = calculate_targets(
            sex=profile.sex,
            age=profile.age,
            weight_kg=profile.weight_kg,
            height_cm=profile.height_cm,
            activity_level=profile.activity_level,
            goal=profile.goal,
        )
        inputs = {
            "sex_for_energy_equation": profile.sex,
            "activity_level": profile.activity_level,
            "nutrition_goal": profile.goal,
            "age": str(profile.age),
            "weight_kg": str(profile.weight_kg),
            "height_cm": str(profile.height_cm),
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
            raise NutritionNotFoundError("Active nutrition targets not found")
        return target

    async def search_foods(self, query: str) -> list[dict[str, Any]]:
        provider = self._food_provider()
        try:
            foods = await provider.search_foods(query)
        except FoodDataProviderError as error:
            raise NutritionFoodDataError(str(error)) from error
        return [food.__dict__ for food in foods]

    async def get_food_catalogue(self) -> list[dict[str, Any]]:
        return await self.repo.list_all_food_catalogue()

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

    def _food_provider(self) -> UsdaFoodDataCentralProvider:
        if self.food_provider is None:
            from .config import settings

            self.food_provider = UsdaFoodDataCentralProvider(settings.USDA_FDC_API_KEY)
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
