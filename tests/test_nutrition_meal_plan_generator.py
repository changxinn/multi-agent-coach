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


def test_meal_plan_prompt_requires_targeted_catalogue_searches_and_pagination():
    assert "several targeted ingredient or food-category" in SYSTEM_PROMPT
    assert "next_cursor" in SYSTEM_PROMPT
    assert "one unfiltered first" in SYSTEM_PROMPT


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
            11: {"allergen_status": "known", "allergen_data": ["gluten"]},
            12: {"allergen_status": "unknown", "allergen_data": None},
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
                            "items": [{"food_cache_id": 11, "grams": 50}],
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
async def test_llm_generator_rejects_food_ids_not_returned_by_catalogue(monkeypatch):
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
                        "items": [{"food_cache_id": 999, "grams": 50}],
                    }
                ]
            },
        )
    )
    monkeypatch.setattr(
        "services.nutrition_agent.app.meal_plan_generator.OpenAI", lambda **_: client
    )
    generator = MealPlanLLMGenerator(Settings(OPENAI_API_KEY="test"), repo)

    with pytest.raises(MealPlanGenerationError, match="unobserved"):
        await generator.generate(
            target={"id": 3},
            profile={},
            start_date=date(2026, 9, 22),
            end_date=date(2026, 9, 22),
            meal_types=["breakfast"],
        )


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
        return_value={11: {"id": 11, "allergen_status": "known", "allergen_data": []}}
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
async def test_service_falls_back_when_llm_selection_cannot_be_materialized():
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
        return_value={11: {"id": 11, "allergen_status": "known", "allergen_data": []}}
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

    assert (
        service.repo.create_meal_plan.await_args.kwargs["generated_plan"]["generator"]
        == "deterministic_catalogue_v1"
    )


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
    repo.get_food_safety_metadata = AsyncMock(
        return_value={29: {"allergen_status": "known", "allergen_data": []}}
    )
    generator = MealPlanLLMGenerator(MagicMock(), repo)

    result = await generator._browse(
        {"cursor": 50, "limit": 25, "query": " tofu "},
        {"allergies": []},
        set(),
    )

    assert result["items"][0]["id"] == 29
    assert result["items"][0]["description"] == "Tofu, firm"
    assert result["next_cursor"] is None
    repo.browse_food_catalogue.assert_awaited_once_with(
        offset=50, limit=25, query=" tofu "
    )
