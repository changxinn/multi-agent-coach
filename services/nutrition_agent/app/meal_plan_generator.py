"""LLM meal-plan selection constrained to the local USDA food cache."""

import asyncio
import json
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from openai import OpenAI

from .config import Settings
from .meal_plan_eligibility import is_compatible_for_meal_plan

logger = logging.getLogger("uvicorn.error")

MEAL_PLAN_MAX_TOOL_CALLS = 16
MEAL_PLAN_PAGE_SIZE = 25
MEAL_PLAN_MAX_PAGE_SIZE = 50
MEAL_PLAN_MAX_GRAMS = Decimal(2000)
MEAL_PLAN_MAX_SUBMISSION_CORRECTIONS = 2
MEAL_PLAN_MAX_CORRECTIONS_PER_CATEGORY = 1

SYSTEM_PROMPT = """
You are Sam, a practical, non-judgmental sports nutrition advisor.
You are one of an agent in a fitness coaching team.
You create varied, alcohol-free meal-plan ingredient selections.
Use tools to get the authoritative context and locally cached USDA foods.
Never invent food names, selection tokens, nutrition values, allergies, or quantities.
Create every requested date/meal slot exactly once.
Before submitting, browse the catalogue with several targeted ingredient or food-category
queries that suit the profile and meal slots (for example, vegetables, fruit, whole grain,
legume, poultry, fish, yoghurt, tofu, or nuts). Do not base a plan on one unfiltered first
page. When a search result has next_cursor, use it to inspect more matching foods when
needed for a varied plan. Do not submit identical meal compositions. Use a different first
ingredient for each meal slot until the eligible catalogue is exhausted; the server rejects
repeated primary foods when you have observed enough eligible alternatives. Prefer varied food
categories across meals and days. Include at least two ingredients in breakfast, lunch, and
dinner when suitable eligible foods are available.
When you have fewer eligible tokens than requested slots, use every currently browsed eligible
token as a first-item selection_token before repeating one as a primary ingredient.
Respect the profile's preferences and restrictions.
Since you are a part of a fitness coaching team, ensure the meal-plan includes healthy options.
Do not select alcoholic beverages or ingredients containing alcohol.
Submit only short selection_token values (for example, food_01) copied exactly from items
returned by browse_cached_usda_foods during this request. Never submit a food description as a
selection_token and never guess, invent, or reuse a token from a different request. If a
submission is rejected, correct the complete plan using only tokens from the current request's
browse results.
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
            "description": "Submit each requested slot with selection tokens returned by browse_cached_usda_foods in this request and gram quantities only.",
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
                                            "selection_token": {
                                                "type": "string",
                                                "minLength": 1,
                                                "maxLength": 100,
                                            },
                                            "grams": {
                                                "type": "number",
                                                "exclusiveMinimum": 0,
                                            },
                                        },
                                        "required": ["selection_token", "grams"],
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
        selection_tokens: dict[str, int] = {}
        submission_corrections: dict[str, int] = {}
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
                    result = await self._browse(arguments, profile, selection_tokens)
                elif tool_call.function.name == "submit_meal_plan":
                    try:
                        meals = self._validate_submission(
                            arguments, context, selection_tokens, request_id=request_id
                        )
                    except MealPlanGenerationError as error:
                        correction_category = _submission_correction_category(error)
                        if (
                            sum(submission_corrections.values())
                            >= MEAL_PLAN_MAX_SUBMISSION_CORRECTIONS
                            or submission_corrections.get(correction_category, 0)
                            >= MEAL_PLAN_MAX_CORRECTIONS_PER_CATEGORY
                        ):
                            raise
                        submission_corrections[correction_category] = (
                            submission_corrections.get(correction_category, 0) + 1
                        )
                        logger.warning(
                            "Meal-plan LLM submission rejected; requesting correction "
                            "request_id=%s round=%d correction=%d reason=%s",
                            request_id,
                            round_number,
                            sum(submission_corrections.values()),
                            error,
                        )
                        result = _submission_correction_result(
                            error,
                            required_slot_count=len(context["required_slots"]),
                            eligible_token_count=len(selection_tokens),
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(result),
                            }
                        )
                        break
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
        selection_tokens: dict[str, int],
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
        eligible = [
            food
            for food in foods
            if _safe_food(food, metadata.get(food["id"]), profile)
        ]
        token_by_food_id = {
            food_id: token for token, food_id in selection_tokens.items()
        }
        for food in eligible:
            if food["id"] in token_by_food_id:
                continue
            token = f"food_{len(selection_tokens) + 1:02d}"
            token_by_food_id[food["id"]] = token
            selection_tokens[token] = food["id"]
        fields = (
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
            "items": [
                {
                    "selection_token": token_by_food_id[food["id"]],
                    **{key: food.get(key) for key in fields},
                }
                for food in eligible
            ],
            "next_cursor": cursor + len(foods) if has_more else None,
        }

    @staticmethod
    def _validate_submission(
        arguments: dict[str, Any],
        context: dict[str, Any],
        selection_tokens: dict[str, int],
        *,
        request_id: str = "unknown",
    ) -> list[dict[str, Any]]:
        meals = arguments.get("meals")
        if not isinstance(meals, list):
            raise MealPlanGenerationError("Meal-plan LLM submitted no meals")
        required = {
            (slot["planned_date"], slot["meal_type"])
            for slot in context["required_slots"]
        }
        submitted: set[tuple[Any, Any]] = set()
        primary_food_ids: list[int] = []
        compositions: set[tuple[int, ...]] = set()
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
            meal_food_ids: list[int] = []
            for item in meal["items"]:
                try:
                    grams = Decimal(str(item.get("grams")))
                except (InvalidOperation, ValueError, TypeError) as error:
                    selection_token = item.get("selection_token")
                    raw_grams = repr(item.get("grams"))[:200]
                    logger.warning(
                        "Meal-plan LLM rejected submitted item request_id=%s "
                        "planned_date=%s meal_type=%s selection_token=%s raw_grams=%s "
                        "reason=invalid_grams",
                        request_id,
                        meal.get("planned_date"),
                        meal.get("meal_type"),
                        selection_token
                        if isinstance(selection_token, str)
                        else "invalid",
                        raw_grams,
                    )
                    raise MealPlanGenerationError(
                        "Meal-plan LLM submitted invalid grams"
                    ) from error
                if (
                    not isinstance(item.get("selection_token"), str)
                    or item["selection_token"] not in selection_tokens
                    or not 0 < grams <= MEAL_PLAN_MAX_GRAMS
                ):
                    selection_token = item.get("selection_token")
                    token_is_string = isinstance(selection_token, str)
                    token_exposed = (
                        token_is_string and selection_token in selection_tokens
                    )
                    logger.warning(
                        "Meal-plan LLM rejected submitted item request_id=%s "
                        "planned_date=%s meal_type=%s selection_token=%s grams=%s "
                        "token_is_string=%s token_exposed=%s grams_valid=%s",
                        request_id,
                        meal.get("planned_date"),
                        meal.get("meal_type"),
                        selection_token if token_is_string else "invalid",
                        grams,
                        token_is_string,
                        token_exposed,
                        0 < grams <= MEAL_PLAN_MAX_GRAMS,
                    )
                    raise MealPlanGenerationError(
                        "Meal-plan LLM submitted an unsafe or unobserved food"
                    )
                meal_food_ids.append(selection_tokens[item["selection_token"]])
            primary_food_ids.append(meal_food_ids[0])
            composition = tuple(sorted(set(meal_food_ids)))
            if composition in compositions and len(selection_tokens) >= len(required):
                raise MealPlanGenerationError(
                    "Meal-plan LLM submitted duplicate meal compositions"
                )
            compositions.add(composition)
        if submitted != required:
            raise MealPlanGenerationError(
                "Meal-plan LLM did not submit every requested meal"
            )
        required_primary_foods = min(len(required), len(selection_tokens))
        if len(set(primary_food_ids)) < required_primary_foods:
            raise MealPlanGenerationError(
                "Meal-plan LLM submitted insufficiently varied primary foods"
            )
        return [
            {
                **meal,
                "items": [
                    {
                        "food_cache_id": selection_tokens[item["selection_token"]],
                        "grams": item["grams"],
                    }
                    for item in meal["items"]
                ],
            }
            for meal in meals
        ]


def _safe_food(
    food: dict[str, Any], metadata: dict[str, Any] | None, profile: dict[str, Any]
) -> bool:
    return bool(
        metadata
        and Decimal(str(food["calories_per_100g"])) > 0
        and is_compatible_for_meal_plan(food, metadata, profile)
    )


def _submission_correction_reason(error: MealPlanGenerationError) -> str:
    """Return a safe, actionable reason without reflecting model-provided values."""
    if str(error) == "Meal-plan LLM submitted an unsafe or unobserved food":
        return "unknown_selection_token"
    if str(error) == "Meal-plan LLM submitted invalid grams":
        return "invalid_grams"
    if str(error) == "Meal-plan LLM submitted duplicate meal compositions":
        return "duplicate_meal_composition"
    if str(error) == "Meal-plan LLM submitted insufficiently varied primary foods":
        return "insufficient_primary_variety"
    return "invalid_submission"


def _submission_correction_category(error: MealPlanGenerationError) -> str:
    """Group retry budgets by actionable correction type."""
    if str(error) in {
        "Meal-plan LLM submitted duplicate meal compositions",
        "Meal-plan LLM submitted insufficiently varied primary foods",
    }:
        return "variety"
    return "validity"


def _submission_correction_result(
    error: MealPlanGenerationError,
    *,
    required_slot_count: int,
    eligible_token_count: int,
) -> dict[str, Any]:
    """Give one sanitized, category-specific correction instruction to the model."""
    reason = _submission_correction_reason(error)
    if _submission_correction_category(error) == "variety":
        required_distinct_primary_foods = min(required_slot_count, eligible_token_count)
        return {
            "accepted": False,
            "correction_required": True,
            "reason": reason,
            "required_distinct_primary_foods": required_distinct_primary_foods,
            "message": (
                "Your complete meal-plan submission needs more variety. Resubmit the complete "
                f"plan using {required_distinct_primary_foods} different first-item "
                "selection_token values before repeating a primary token. Do not submit "
                "identical meal compositions. You may repeat a primary token only after all "
                "currently browsed eligible tokens have been used as a primary ingredient."
            ),
        }
    return {
        "accepted": False,
        "correction_required": True,
        "reason": reason,
        "message": (
            "Your complete meal-plan submission was rejected. Submit the complete plan again "
            "using only short selection_token values (for example, food_01) returned by "
            "browse_cached_usda_foods during this request. Do not put a food description in "
            "selection_token. Browse again if you cannot locate a valid token. Use numeric "
            "grams greater than 0 and no more than 2000."
        ),
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
