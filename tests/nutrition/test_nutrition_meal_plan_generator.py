import asyncio
import json
import threading
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.nutrition_agent.app.config import Settings
from services.nutrition_agent.app.meal_plan_generator import (
    SYSTEM_PROMPT,
    MealPlanGenerationError,
    MealPlanLLMGenerator,
)
from services.nutrition_agent.app.schemas import MealPlanGenerateRequest
from services.nutrition_agent.app.service import NutritionService


def _call(name, arguments, call_id="call-1"):
    call = MagicMock()
    call.id = call_id
    call.function.name = name
    call.function.arguments = json.dumps(arguments)
    return call


def _completion(*calls):
    completion = MagicMock()
    completion.choices[0].message.tool_calls = list(calls)
    completion.choices[0].message.model_dump.return_value = {
        "role": "assistant",
        "tool_calls": [],
    }
    return completion


def approved_metadata(*, allergens=(), strict_suitability=None):
    return {
        "review_status": "approved",
        "allergen_status": "known",
        "known_allergens": list(allergens),
        "strict_suitability": strict_suitability or {},
    }


def test_meal_plan_prompt_requires_targeted_catalogue_searches_and_pagination():
    assert "several targeted ingredient or food-category" in SYSTEM_PROMPT
    assert "next_cursor" in SYSTEM_PROMPT
    assert "one unfiltered first" in SYSTEM_PROMPT
    assert "Do not submit identical meal compositions" in SYSTEM_PROMPT
    assert (
        "repeated primary foods when you have observed enough eligible alternatives"
        in SYSTEM_PROMPT
    )
    assert "short selection_token values (for example, food_01)" in SYSTEM_PROMPT
    assert "Never submit a food description as a" in SYSTEM_PROMPT


def test_llm_submission_rejects_duplicate_compositions_and_primary_foods():
    context = {
        "required_slots": [
            {"planned_date": "2026-09-22", "meal_type": "breakfast"},
            {"planned_date": "2026-09-22", "meal_type": "lunch"},
        ]
    }

    with pytest.raises(MealPlanGenerationError, match="duplicate meal compositions"):
        MealPlanLLMGenerator._validate_submission(
            {
                "meals": [
                    {
                        "planned_date": "2026-09-22",
                        "meal_type": "breakfast",
                        "items": [{"selection_token": "token-11", "grams": 300}],
                    },
                    {
                        "planned_date": "2026-09-22",
                        "meal_type": "lunch",
                        "items": [{"selection_token": "token-11", "grams": 250}],
                    },
                ]
            },
            context,
            {"token-11": 11, "token-12": 12},
        )

    with pytest.raises(
        MealPlanGenerationError, match="insufficiently varied primary foods"
    ):
        MealPlanLLMGenerator._validate_submission(
            {
                "meals": [
                    {
                        "planned_date": "2026-09-22",
                        "meal_type": "breakfast",
                        "items": [
                            {"selection_token": "token-11", "grams": 300},
                            {"selection_token": "token-12", "grams": 50},
                        ],
                    },
                    {
                        "planned_date": "2026-09-22",
                        "meal_type": "lunch",
                        "items": [
                            {"selection_token": "token-11", "grams": 250},
                            {"selection_token": "token-13", "grams": 50},
                        ],
                    },
                ]
            },
            context,
            {"token-11": 11, "token-12": 12, "token-13": 13},
        )


def test_llm_submission_allows_repetition_only_after_eligible_foods_are_exhausted():
    context = {
        "required_slots": [
            {"planned_date": "2026-09-22", "meal_type": "breakfast"},
            {"planned_date": "2026-09-22", "meal_type": "lunch"},
            {"planned_date": "2026-09-22", "meal_type": "dinner"},
        ]
    }

    meals = MealPlanLLMGenerator._validate_submission(
        {
            "meals": [
                {
                    "planned_date": "2026-09-22",
                    "meal_type": "breakfast",
                    "items": [{"selection_token": "token-11", "grams": 300}],
                },
                {
                    "planned_date": "2026-09-22",
                    "meal_type": "lunch",
                    "items": [{"selection_token": "token-12", "grams": 250}],
                },
                {
                    "planned_date": "2026-09-22",
                    "meal_type": "dinner",
                    "items": [{"selection_token": "token-11", "grams": 275}],
                },
            ]
        },
        context,
        {"token-11": 11, "token-12": 12},
    )

    assert len(meals) == 3


@pytest.mark.asyncio
async def test_llm_generator_does_not_block_event_loop_during_provider_request(
    monkeypatch,
):
    request_started = threading.Event()
    release_request = threading.Event()
    client = MagicMock()

    def blocking_create(**_):
        request_started.set()
        assert release_request.wait(timeout=1)
        return _completion()

    client.chat.completions.create.side_effect = blocking_create
    monkeypatch.setattr(
        "services.nutrition_agent.app.meal_plan_generator.OpenAI", lambda **_: client
    )
    generator = MealPlanLLMGenerator(Settings(OPENAI_API_KEY="test"), MagicMock())

    generation = asyncio.create_task(
        generator.generate(
            target={"id": 3},
            profile={},
            start_date=date(2026, 9, 22),
            end_date=date(2026, 9, 22),
            meal_types=["breakfast"],
        )
    )
    assert await asyncio.to_thread(request_started.wait, 0.5)

    other_work_completed = asyncio.Event()

    async def other_work():
        await asyncio.sleep(0)
        other_work_completed.set()

    other_work_task = asyncio.create_task(other_work())
    await asyncio.wait_for(other_work_completed.wait(), timeout=0.1)
    release_request.set()
    await other_work_task

    with pytest.raises(MealPlanGenerationError, match="did not submit a plan"):
        await generation


@pytest.mark.asyncio
async def test_llm_generator_browses_catalogue_and_only_accepts_exposed_safe_ids(
    monkeypatch, caplog
):
    repo = MagicMock()
    repo.browse_food_catalogue = AsyncMock(
        return_value=(
            [
                {
                    "id": 11,
                    "description": "Oats",
                    "calories_per_100g": Decimal(400),
                    "protein_g_per_100g": Decimal(10),
                    "carbohydrate_g_per_100g": Decimal(70),
                    "fat_g_per_100g": Decimal(8),
                    "fiber_g_per_100g": Decimal(10),
                },
                {
                    "id": 12,
                    "description": "Milk",
                    "calories_per_100g": Decimal(60),
                    "protein_g_per_100g": Decimal(3),
                    "carbohydrate_g_per_100g": Decimal(5),
                    "fat_g_per_100g": Decimal(3),
                },
            ],
            True,
        )
    )
    repo.get_food_safety_metadata = AsyncMock(
        return_value={
            11: approved_metadata(allergens=["gluten"]),
            12: {"review_status": "pending", "allergen_status": "unknown"},
        }
    )
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _completion(_call("browse_cached_usda_foods", {"cursor": 0, "limit": 25})),
        _completion(
            _call(
                "submit_meal_plan",
                {
                    "meals": [
                        {
                            "planned_date": "2026-09-22",
                            "meal_type": "breakfast",
                            "items": [{"selection_token": "food_01", "grams": 50}],
                        }
                    ]
                },
            )
        ),
    ]
    monkeypatch.setattr(
        "services.nutrition_agent.app.meal_plan_generator.OpenAI", lambda **_: client
    )
    generator = MealPlanLLMGenerator(Settings(OPENAI_API_KEY="test"), repo)

    with caplog.at_level("INFO", logger="uvicorn.error"):
        result = await generator.generate(
            target={"id": 3},
            profile={"allergies": ["milk"]},
            start_date=date(2026, 9, 22),
            end_date=date(2026, 9, 22),
            meal_types=["breakfast"],
            request_id="request-123",
        )

    assert result[0]["items"][0]["food_cache_id"] == 11
    assert repo.browse_food_catalogue.await_args.kwargs == {
        "offset": 0,
        "limit": 25,
        "query": None,
    }
    assert "Meal-plan LLM round started request_id=request-123 round=1" in caplog.text
    assert "tool_names=browse_cached_usda_foods" in caplog.text
    assert "Meal-plan LLM submission accepted request_id=request-123" in caplog.text
    assert "milk" not in caplog.text


@pytest.mark.asyncio
async def test_llm_generator_corrects_a_submission_with_an_unobserved_token(
    monkeypatch, caplog
):
    repo = MagicMock()
    repo.browse_food_catalogue = AsyncMock(
        return_value=(
            [
                {
                    "id": 11,
                    "description": "Oats",
                    "calories_per_100g": Decimal(400),
                    "protein_g_per_100g": Decimal(10),
                    "carbohydrate_g_per_100g": Decimal(70),
                    "fat_g_per_100g": Decimal(8),
                }
            ],
            False,
        )
    )
    repo.get_food_safety_metadata = AsyncMock(return_value={11: approved_metadata()})
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _completion(_call("browse_cached_usda_foods", {"cursor": 0, "limit": 25})),
        _completion(
            _call(
                "submit_meal_plan",
                {
                    "meals": [
                        {
                            "planned_date": "2026-09-22",
                            "meal_type": "breakfast",
                            "items": [{"selection_token": "invented", "grams": 50}],
                        }
                    ]
                },
            )
        ),
        _completion(
            _call(
                "submit_meal_plan",
                {
                    "meals": [
                        {
                            "planned_date": "2026-09-22",
                            "meal_type": "breakfast",
                            "items": [{"selection_token": "food_01", "grams": 50}],
                        }
                    ]
                },
            )
        ),
    ]
    monkeypatch.setattr(
        "services.nutrition_agent.app.meal_plan_generator.OpenAI", lambda **_: client
    )
    generator = MealPlanLLMGenerator(Settings(OPENAI_API_KEY="test"), repo)

    with (
        caplog.at_level("WARNING", logger="uvicorn.error"),
    ):
        result = await generator.generate(
            target={"id": 3},
            profile={"allergies": ["milk"]},
            start_date=date(2026, 9, 22),
            end_date=date(2026, 9, 22),
            meal_types=["breakfast"],
            request_id="request-123",
        )

    assert result[0]["items"] == [{"food_cache_id": 11, "grams": 50}]
    assert "Meal-plan LLM rejected submitted item request_id=request-123" in caplog.text
    assert "planned_date=2026-09-22 meal_type=breakfast" in caplog.text
    assert "selection_token=invented grams=50" in caplog.text
    assert "token_is_string=True token_exposed=False grams_valid=True" in caplog.text
    assert (
        "submission rejected; requesting correction request_id=request-123"
        in caplog.text
    )
    correction_messages = client.chat.completions.create.call_args_list[2].kwargs[
        "messages"
    ]
    correction_message = next(
        message
        for message in reversed(correction_messages)
        if message["role"] == "tool"
    )
    correction_result = json.loads(correction_message["content"])
    assert correction_result["reason"] == "unknown_selection_token"
    assert "Do not put a food description" in correction_result["message"]
    assert "invented" not in correction_message["content"]
    assert "milk" not in caplog.text


@pytest.mark.asyncio
async def test_llm_generator_allows_one_validity_and_one_variety_correction(
    monkeypatch,
):
    repo = MagicMock()
    repo.browse_food_catalogue = AsyncMock(
        return_value=(
            [
                {
                    "id": 11,
                    "description": "Oats",
                    "calories_per_100g": Decimal(400),
                    "protein_g_per_100g": Decimal(10),
                    "carbohydrate_g_per_100g": Decimal(70),
                    "fat_g_per_100g": Decimal(8),
                },
                {
                    "id": 12,
                    "description": "Lentils",
                    "calories_per_100g": Decimal(116),
                    "protein_g_per_100g": Decimal(9),
                    "carbohydrate_g_per_100g": Decimal(20),
                    "fat_g_per_100g": Decimal(0),
                },
            ],
            False,
        )
    )
    repo.get_food_safety_metadata = AsyncMock(
        return_value={11: approved_metadata(), 12: approved_metadata()}
    )
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _completion(_call("browse_cached_usda_foods", {"cursor": 0, "limit": 25})),
        _completion(
            _call(
                "submit_meal_plan",
                {
                    "meals": [
                        {
                            "planned_date": "2026-09-22",
                            "meal_type": "breakfast",
                            "items": [{"selection_token": "invented", "grams": 50}],
                        },
                        {
                            "planned_date": "2026-09-22",
                            "meal_type": "lunch",
                            "items": [{"selection_token": "food_02", "grams": 50}],
                        },
                    ]
                },
            )
        ),
        _completion(
            _call(
                "submit_meal_plan",
                {
                    "meals": [
                        {
                            "planned_date": "2026-09-22",
                            "meal_type": "breakfast",
                            "items": [{"selection_token": "food_01", "grams": 50}],
                        },
                        {
                            "planned_date": "2026-09-22",
                            "meal_type": "lunch",
                            "items": [{"selection_token": "food_01", "grams": 75}],
                        },
                    ]
                },
            )
        ),
        _completion(
            _call(
                "submit_meal_plan",
                {
                    "meals": [
                        {
                            "planned_date": "2026-09-22",
                            "meal_type": "breakfast",
                            "items": [{"selection_token": "food_01", "grams": 50}],
                        },
                        {
                            "planned_date": "2026-09-22",
                            "meal_type": "lunch",
                            "items": [{"selection_token": "food_02", "grams": 75}],
                        },
                    ]
                },
            )
        ),
    ]
    monkeypatch.setattr(
        "services.nutrition_agent.app.meal_plan_generator.OpenAI", lambda **_: client
    )
    generator = MealPlanLLMGenerator(Settings(OPENAI_API_KEY="test"), repo)

    result = await generator.generate(
        target={"id": 3},
        profile={},
        start_date=date(2026, 9, 22),
        end_date=date(2026, 9, 22),
        meal_types=["breakfast", "lunch"],
    )

    assert [meal["items"][0]["food_cache_id"] for meal in result] == [11, 12]
    final_messages = client.chat.completions.create.call_args_list[3].kwargs["messages"]
    correction_results = [
        json.loads(message["content"])
        for message in final_messages
        if message["role"] == "tool" and "correction_required" in message["content"]
    ]
    assert correction_results == [
        {
            "accepted": False,
            "correction_required": True,
            "reason": "unknown_selection_token",
            "message": correction_results[0]["message"],
        },
        {
            "accepted": False,
            "correction_required": True,
            "reason": "duplicate_meal_composition",
            "required_distinct_primary_foods": 2,
            "message": correction_results[1]["message"],
        },
    ]
    assert (
        "using 2 different first-item selection_token values"
        in correction_results[1]["message"]
    )


@pytest.mark.asyncio
async def test_llm_generator_rejects_a_second_variety_failure(monkeypatch):
    repo = MagicMock()
    repo.browse_food_catalogue = AsyncMock(
        return_value=(
            [
                {
                    "id": 11,
                    "description": "Oats",
                    "calories_per_100g": Decimal(400),
                    "protein_g_per_100g": Decimal(10),
                    "carbohydrate_g_per_100g": Decimal(70),
                    "fat_g_per_100g": Decimal(8),
                },
                {
                    "id": 12,
                    "description": "Lentils",
                    "calories_per_100g": Decimal(116),
                    "protein_g_per_100g": Decimal(9),
                    "carbohydrate_g_per_100g": Decimal(20),
                    "fat_g_per_100g": Decimal(0),
                },
            ],
            False,
        )
    )
    repo.get_food_safety_metadata = AsyncMock(
        return_value={11: approved_metadata(), 12: approved_metadata()}
    )
    invalid_variety_submission = {
        "meals": [
            {
                "planned_date": "2026-09-22",
                "meal_type": "breakfast",
                "items": [{"selection_token": "food_01", "grams": 50}],
            },
            {
                "planned_date": "2026-09-22",
                "meal_type": "lunch",
                "items": [{"selection_token": "food_01", "grams": 75}],
            },
        ]
    }
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _completion(_call("browse_cached_usda_foods", {"cursor": 0, "limit": 25})),
        _completion(_call("submit_meal_plan", invalid_variety_submission)),
        _completion(_call("submit_meal_plan", invalid_variety_submission)),
    ]
    monkeypatch.setattr(
        "services.nutrition_agent.app.meal_plan_generator.OpenAI", lambda **_: client
    )
    generator = MealPlanLLMGenerator(Settings(OPENAI_API_KEY="test"), repo)

    with pytest.raises(MealPlanGenerationError, match="duplicate meal compositions"):
        await generator.generate(
            target={"id": 3},
            profile={},
            start_date=date(2026, 9, 22),
            end_date=date(2026, 9, 22),
            meal_types=["breakfast", "lunch"],
        )

    assert client.chat.completions.create.call_count == 3


@pytest.mark.asyncio
async def test_llm_generator_logs_sanitized_diagnostics_for_invalid_grams(
    monkeypatch, caplog
):
    repo = MagicMock()
    client = MagicMock()
    client.chat.completions.create.return_value = _completion(
        _call(
            "submit_meal_plan",
            {
                "meals": [
                    {
                        "planned_date": "2026-09-22",
                        "meal_type": "breakfast",
                        "items": [
                            {"selection_token": "token-11", "grams": "one serving"}
                        ],
                    }
                ]
            },
        )
    )
    monkeypatch.setattr(
        "services.nutrition_agent.app.meal_plan_generator.OpenAI", lambda **_: client
    )
    generator = MealPlanLLMGenerator(Settings(OPENAI_API_KEY="test"), repo)

    with (
        caplog.at_level("WARNING", logger="uvicorn.error"),
        pytest.raises(MealPlanGenerationError, match="invalid grams"),
    ):
        await generator.generate(
            target={"id": 3},
            profile={"allergies": ["milk"]},
            start_date=date(2026, 9, 22),
            end_date=date(2026, 9, 22),
            meal_types=["breakfast"],
            request_id="request-456",
        )

    assert "Meal-plan LLM rejected submitted item request_id=request-456" in caplog.text
    assert "planned_date=2026-09-22 meal_type=breakfast" in caplog.text
    assert "selection_token=token-11 raw_grams='one serving'" in caplog.text
    assert "reason=invalid_grams" in caplog.text
    assert "milk" not in caplog.text


@pytest.mark.asyncio
async def test_llm_generator_logs_sanitized_request_and_provider_failure(
    monkeypatch, caplog
):
    repo = MagicMock()
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("model is unavailable")
    openai_factory = MagicMock(return_value=client)
    monkeypatch.setattr(
        "services.nutrition_agent.app.meal_plan_generator.OpenAI", openai_factory
    )
    generator = MealPlanLLMGenerator(
        Settings(
            OPENAI_API_KEY="secret-api-key",
            OPENAI_BASE_URL="https://provider.example/v1",
            LLM_MODEL="test-model",
            NUTRITION_LLM_DEBUG_LOG_REQUESTS=True,
        ),
        repo,
    )

    with (
        caplog.at_level("WARNING", logger="uvicorn.error"),
        pytest.raises(MealPlanGenerationError, match="request failed"),
    ):
        await generator.generate(
            target={"id": 3},
            profile={},
            start_date=date(2026, 9, 22),
            end_date=date(2026, 9, 22),
            meal_types=["breakfast"],
            request_id="request-123",
        )

    assert "Meal-plan LLM request request_id=request-123 round=1" in caplog.text
    assert "'model': 'test-model'" in caplog.text
    assert "'tools':" in caplog.text
    assert "secret-api-key" not in caplog.text
    assert "Meal-plan LLM request failed request_id=request-123 round=1" in caplog.text
    assert "error_type=RuntimeError error=model is unavailable" in caplog.text
    openai_factory.assert_called_once_with(
        api_key="secret-api-key", base_url="https://provider.example/v1"
    )


@pytest.mark.asyncio
async def test_service_materializes_llm_items_from_authoritative_cached_foods():
    generator = MagicMock()
    generator.generate = AsyncMock(
        return_value=[
            {
                "planned_date": "2026-09-22",
                "meal_type": "breakfast",
                "items": [{"food_cache_id": 11, "grams": 50}],
            }
        ]
    )
    service = NutritionService(AsyncMock(), meal_plan_generator=generator)
    service.repo.get_active_target = AsyncMock(
        return_value={
            "id": 3,
            "calorie_target_kcal": Decimal(1800),
            "protein_target_g": Decimal(120),
            "carbohydrate_target_g": Decimal(180),
            "fat_target_g": Decimal(60),
            "fiber_target_g": Decimal(30),
        }
    )
    service.repo.get_food_catalogue_by_ids = AsyncMock(
        return_value={
            11: {
                "id": 11,
                "description": "Oats",
                "calories_per_100g": Decimal(400),
                "protein_g_per_100g": Decimal(10),
                "carbohydrate_g_per_100g": Decimal(70),
                "fat_g_per_100g": Decimal(8),
                "fiber_g_per_100g": Decimal(10),
            }
        }
    )
    service.repo.get_food_safety_metadata = AsyncMock(
        return_value={11: approved_metadata()}
    )
    service.repo.get_target_snapshot = AsyncMock(return_value={"id": 3})
    service.repo.create_meal_plan = AsyncMock(return_value={"id": 42})

    await service.generate_meal_plan(
        7,
        MealPlanGenerateRequest(
            user_id=7,
            start_date="2026-09-22",
            end_date="2026-09-22",
            meal_types=["breakfast"],
        ),
    )

    args = service.repo.create_meal_plan.await_args.kwargs
    assert args["generated_plan"]["generator"] == "llm_cached_usda_tools_v1"
    assert args["planned_meals"][0]["items"][0]["calories"] == Decimal("200.00")


@pytest.mark.asyncio
async def test_service_falls_back_when_llm_selection_cannot_be_materialized(caplog):
    generator = MagicMock()
    generator.generate = AsyncMock(
        return_value=[
            {
                "planned_date": "2026-09-22",
                "meal_type": "breakfast",
                "items": [{"food_cache_id": 99, "grams": 50}],
            }
        ]
    )
    service = NutritionService(AsyncMock(), meal_plan_generator=generator)
    service.repo.get_active_target = AsyncMock(
        return_value={
            "id": 3,
            "calorie_target_kcal": Decimal(1800),
            "protein_target_g": Decimal(120),
            "carbohydrate_target_g": Decimal(180),
            "fat_target_g": Decimal(60),
            "fiber_target_g": Decimal(30),
        }
    )
    service.repo.get_food_catalogue_by_ids = AsyncMock(return_value={})
    service.repo.list_food_catalogue = AsyncMock(
        return_value=[
            {
                "id": 11,
                "description": "Oats",
                "calories_per_100g": Decimal(400),
                "protein_g_per_100g": Decimal(10),
                "carbohydrate_g_per_100g": Decimal(70),
                "fat_g_per_100g": Decimal(8),
                "fiber_g_per_100g": Decimal(10),
            }
        ]
    )
    service.repo.get_food_safety_metadata = AsyncMock(
        return_value={11: approved_metadata()}
    )
    service.repo.get_target_snapshot = AsyncMock(return_value={"id": 3})
    service.repo.create_meal_plan = AsyncMock(return_value={"id": 42})

    with caplog.at_level("WARNING", logger="uvicorn.error"):
        await service.generate_meal_plan(
            7,
            MealPlanGenerateRequest(
                user_id=7,
                start_date="2026-09-22",
                end_date="2026-09-22",
                meal_types=["breakfast"],
            ),
            request_id="request-123",
        )

    assert (
        service.repo.create_meal_plan.await_args.kwargs["generated_plan"]["generator"]
        == "deterministic_catalogue_v1"
    )
    assert "request_id=request-123" in caplog.text
    assert "reason=LLM-selected food is not in the local catalogue" in caplog.text


@pytest.mark.asyncio
async def test_service_logs_llm_generation_failure_reason_without_payload(caplog):
    generator = MagicMock()
    generator.generate = AsyncMock(
        side_effect=MealPlanGenerationError(
            "Meal-plan LLM submitted an unsafe or unobserved food"
        )
    )
    service = NutritionService(AsyncMock(), meal_plan_generator=generator)
    payload = MealPlanGenerateRequest(
        user_id=7,
        start_date="2026-09-22",
        end_date="2026-09-22",
        meal_types=["breakfast"],
    )

    with caplog.at_level("WARNING", logger="uvicorn.error"):
        result = await service._try_generate_llm_meals(
            {"id": 3}, payload, request_id="request-123"
        )

    assert result is None
    assert "request_id=request-123" in caplog.text
    assert "reason=Meal-plan LLM submitted an unsafe or unobserved food" in caplog.text


@pytest.mark.asyncio
async def test_llm_generator_can_search_and_continue_a_later_catalogue_page():
    repo = MagicMock()
    tofu = {
        "id": 29,
        "description": "Tofu, firm",
        "calories_per_100g": Decimal(144),
        "protein_g_per_100g": Decimal(17),
        "carbohydrate_g_per_100g": Decimal(3),
        "fat_g_per_100g": Decimal(9),
    }
    repo.browse_food_catalogue = AsyncMock(return_value=([tofu], False))
    repo.get_food_safety_metadata = AsyncMock(return_value={29: approved_metadata()})
    generator = MealPlanLLMGenerator(MagicMock(), repo)

    selection_tokens: dict[str, int] = {}
    result = await generator._browse(
        {"cursor": 50, "limit": 25, "query": " tofu "},
        {"allergies": []},
        selection_tokens,
    )

    assert result["items"][0]["selection_token"] in selection_tokens
    assert result["items"][0]["selection_token"] == "food_01"
    assert selection_tokens[result["items"][0]["selection_token"]] == 29
    assert result["items"][0]["description"] == "Tofu, firm"
    assert result["next_cursor"] is None
    repo.browse_food_catalogue.assert_awaited_once_with(
        offset=50, limit=25, query=" tofu "
    )
