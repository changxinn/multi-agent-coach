"""LLM meal-plan selection constrained to the local USDA food cache."""

import asyncio
import json
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from openai import OpenAI

from .config import Settings
from .meal_plan_eligibility import is_eligible_for_meal_plan

logger = logging.getLogger("uvicorn.error")

MEAL_PLAN_MAX_TOOL_CALLS = 16
MEAL_PLAN_PAGE_SIZE = 25
MEAL_PLAN_MAX_PAGE_SIZE = 50
MEAL_PLAN_MAX_GRAMS = Decimal(2000)

SYSTEM_PROMPT = """
You are Sam, a practical, non-judgmental sports nutrition advisor.
You are one of an agent in a fitness coaching team.
You create varied, alcohol-free meal-plan ingredient selections.
Use tools to get the authoritative context and locally cached USDA foods.
Never invent food names, IDs, nutrition values, allergies, or quantities.
Create every requested date/meal slot exactly once.
Before submitting, browse the catalogue with several targeted ingredient or food-category
queries that suit the profile and meal slots (for example, vegetables, fruit, whole grain,
legume, poultry, fish, yoghurt, tofu, or nuts). Do not base a plan on one unfiltered first
page. When a search result has next_cursor, use it to inspect more matching foods when
needed for a varied plan. Prefer varied foods across meals and days.
Respect the profile's preferences and restrictions.
Since you are a part of a fitness coaching team, ensure the meal-plan includes healthy options.
Do not select alcoholic beverages or ingredients containing alcohol.
Submit only food IDs returned by catalogue tools and gram quantities.
Do not provide medical advice.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_generation_context",
            "description": "Get the authoritative profile, target snapshot, dates, and meal slots.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_cached_usda_foods",
            "description": "Search and page through eligible locally cached USDA foods. Use targeted ingredient/category queries; query filters descriptions and next_cursor continues that query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cursor": {"type": "integer", "minimum": 0},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MEAL_PLAN_MAX_PAGE_SIZE,
                    },
                    "query": {"type": "string", "maxLength": 100},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_meal_plan",
            "description": "Submit each requested slot with cached food IDs and grams only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "meals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "planned_date": {"type": "string", "format": "date"},
                                "meal_type": {
                                    "type": "string",
                                    "enum": ["breakfast", "lunch", "dinner", "snack"],
                                },
                                "items": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "food_cache_id": {
                                                "type": "integer",
                                                "minimum": 1,
                                            },
                                            "grams": {
                                                "type": "number",
                                                "exclusiveMinimum": 0,
                                            },
                                        },
                                        "required": ["food_cache_id", "grams"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["planned_date", "meal_type", "items"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["meals"],
                "additionalProperties": False,
            },
        },
    },
]


class MealPlanGenerationError(Exception):
    """The model did not produce a safe, tool-grounded plan."""


class MealPlanLLMGenerator:
    """Run a bounded native OpenAI tool loop over cached USDA food records."""

    def __init__(self, settings: Settings, repo: Any):
        self.settings = settings
        self.repo = repo

    async def generate(
        self,
        *,
        target: dict[str, Any],
        profile: dict[str, Any],
        start_date: date,
        end_date: date,
        meal_types: list[str],
        request_id: str = "missing",
    ) -> list[dict[str, Any]]:
        if (
            not self.settings.NUTRITION_LLM_ENABLED
            or not self.settings.NUTRITION_MEAL_PLAN_LLM_ENABLED
            or not self.settings.OPENAI_API_KEY
        ):
            raise MealPlanGenerationError("Meal-plan LLM generation is disabled")
        context = {
            "profile": profile,
            "target_snapshot": _jsonable(target),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "meal_types": meal_types,
            "required_slots": [
                {
                    "planned_date": (start_date + timedelta(days=offset)).isoformat(),
                    "meal_type": meal_type,
                }
                for offset in range((end_date - start_date).days + 1)
                for meal_type in meal_types
            ],
        }
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Generate the requested meal plan with the available tools.",
            },
        ]
        exposed_food_ids: set[int] = set()
        client_kwargs: dict[str, str] = {"api_key": self.settings.OPENAI_API_KEY}
        if self.settings.OPENAI_BASE_URL:
            client_kwargs["base_url"] = self.settings.OPENAI_BASE_URL
        client = OpenAI(**client_kwargs)
        for round_number in range(1, MEAL_PLAN_MAX_TOOL_CALLS + 1):
            logger.info(
                "Meal-plan LLM round started request_id=%s round=%d",
                request_id,
                round_number,
            )
            request_kwargs = {
                "model": self.settings.LLM_MODEL,
                "max_completion_tokens": self.settings.NUTRITION_MEAL_PLAN_LLM_MAX_COMPLETION_TOKENS,
                "reasoning_effort": self.settings.NUTRITION_LLM_REASONING_EFFORT,
                "messages": messages,
                "tools": TOOLS,
                "parallel_tool_calls": False,
            }
            if self.settings.NUTRITION_LLM_DEBUG_LOG_REQUESTS:
                logger.warning(
                    "Meal-plan LLM request request_id=%s round=%d request=%r",
                    request_id,
                    round_number,
                    request_kwargs,
                )
            try:
                completion = await asyncio.to_thread(
                    client.chat.completions.create, **request_kwargs
                )
            except Exception as error:
                logger.warning(
                    "Meal-plan LLM request failed request_id=%s round=%d model=%s "
                    "error_type=%s error=%s",
                    request_id,
                    round_number,
                    self.settings.LLM_MODEL,
                    type(error).__name__,
                    error,
                )
                raise MealPlanGenerationError("Meal-plan LLM request failed") from error
            message = completion.choices[0].message
            tool_calls = message.tool_calls or []
            if not tool_calls:
                raise MealPlanGenerationError("Meal-plan LLM did not submit a plan")
            logger.info(
                "Meal-plan LLM tools requested request_id=%s round=%d tool_names=%s",
                request_id,
                round_number,
                ",".join(call.function.name for call in tool_calls),
            )
            messages.append(message.model_dump(exclude_none=True))
            for tool_call in tool_calls:
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError as error:
                    raise MealPlanGenerationError(
                        "Meal-plan LLM supplied invalid tool arguments"
                    ) from error
                if tool_call.function.name == "get_generation_context":
                    result: dict[str, Any] = context
                elif tool_call.function.name == "browse_cached_usda_foods":
                    result = await self._browse(arguments, profile, exposed_food_ids)
                elif tool_call.function.name == "submit_meal_plan":
                    meals = self._validate_submission(
                        arguments, context, exposed_food_ids
                    )
                    logger.info(
                        "Meal-plan LLM submission accepted request_id=%s round=%d meal_count=%d",
                        request_id,
                        round_number,
                        len(meals),
                    )
                    return meals
                else:
                    raise MealPlanGenerationError(
                        "Meal-plan LLM requested an unsupported tool"
                    )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, default=str),
                    }
                )
        raise MealPlanGenerationError("Meal-plan LLM exceeded the tool-call limit")

    async def _browse(
        self,
        arguments: dict[str, Any],
        profile: dict[str, Any],
        exposed_food_ids: set[int],
    ) -> dict[str, Any]:
        cursor, limit, query = (
            arguments.get("cursor", 0),
            arguments.get("limit", MEAL_PLAN_PAGE_SIZE),
            arguments.get("query"),
        )
        if (
            not isinstance(cursor, int)
            or cursor < 0
            or not isinstance(limit, int)
            or not isinstance(query, (str, type(None)))
        ):
            raise MealPlanGenerationError(
                "Meal-plan LLM supplied invalid catalogue pagination"
            )
        foods, has_more = await self.repo.browse_food_catalogue(
            offset=cursor,
            limit=min(max(limit, 1), MEAL_PLAN_MAX_PAGE_SIZE),
            query=query,
        )
        metadata = await self.repo.get_food_safety_metadata(
            {food["id"] for food in foods}
        )
        allergies = _normalised_values(profile.get("allergies"))
        eligible = [
            food
            for food in foods
            if _safe_food(food, metadata.get(food["id"]), allergies)
        ]
        exposed_food_ids.update(food["id"] for food in eligible)
        fields = (
            "id",
            "description",
            "serving_size_g",
            "serving_description",
            "calories_per_100g",
            "protein_g_per_100g",
            "carbohydrate_g_per_100g",
            "fat_g_per_100g",
            "fiber_g_per_100g",
        )
        return {
            "items": [{key: food.get(key) for key in fields} for food in eligible],
            "next_cursor": cursor + len(foods) if has_more else None,
        }

    @staticmethod
    def _validate_submission(
        arguments: dict[str, Any], context: dict[str, Any], exposed_food_ids: set[int]
    ) -> list[dict[str, Any]]:
        meals = arguments.get("meals")
        if not isinstance(meals, list):
            raise MealPlanGenerationError("Meal-plan LLM submitted no meals")
        required = {
            (slot["planned_date"], slot["meal_type"])
            for slot in context["required_slots"]
        }
        submitted: set[tuple[Any, Any]] = set()
        for meal in meals:
            if (
                not isinstance(meal, dict)
                or not isinstance(meal.get("items"), list)
                or not meal["items"]
            ):
                raise MealPlanGenerationError("Meal-plan LLM submitted an invalid meal")
            slot = (meal.get("planned_date"), meal.get("meal_type"))
            if slot not in required or slot in submitted:
                raise MealPlanGenerationError(
                    "Meal-plan LLM submitted invalid or duplicate meal slots"
                )
            submitted.add(slot)
            for item in meal["items"]:
                try:
                    grams = Decimal(str(item.get("grams")))
                except (InvalidOperation, ValueError, TypeError) as error:
                    raise MealPlanGenerationError(
                        "Meal-plan LLM submitted invalid grams"
                    ) from error
                if (
                    not isinstance(item.get("food_cache_id"), int)
                    or item["food_cache_id"] not in exposed_food_ids
                    or not 0 < grams <= MEAL_PLAN_MAX_GRAMS
                ):
                    raise MealPlanGenerationError(
                        "Meal-plan LLM submitted an unsafe or unobserved food"
                    )
        if submitted != required:
            raise MealPlanGenerationError(
                "Meal-plan LLM did not submit every requested meal"
            )
        return meals


def _safe_food(
    food: dict[str, Any], metadata: dict[str, Any] | None, allergies: set[str]
) -> bool:
    if (
        not is_eligible_for_meal_plan(food)
        or not metadata
        or Decimal(str(food["calories_per_100g"])) <= 0
    ):
        return False
    if metadata.get("allergen_status") == "unknown":
        return not allergies
    return metadata.get("allergen_status") == "known" and not (
        allergies & _allergen_values(metadata.get("allergen_data"))
    )


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
        return set().union(*(_allergen_values(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_allergen_values(item) for item in value))
    return set()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
