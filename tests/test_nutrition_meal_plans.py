from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.nutrition_agent.app.repository import NutritionRepository
from services.nutrition_agent.app.schemas import (
    MealPlanCreateRequest,
    MealPlanGenerateRequest,
)
from services.nutrition_agent.app.service import (
    NutritionMealPlanSafetyError,
    NutritionMealPlanTransitionError,
    NutritionNotFoundError,
    NutritionProfileIncompleteError,
    NutritionService,
)


def planned_meal(**overrides):
    return {
        "planned_date": "2026-09-22",
        "meal_type": "breakfast",
        "calorie_target_kcal": "500",
        "protein_target_g": "30",
        "carbohydrate_target_g": "50",
        "fat_target_g": "15",
        "fiber_target_g": "8",
        "items": [
            {
                "food_name": "Oats",
                "quantity": "50",
                "unit": "g",
                "calories": "190",
                "protein_g": "6",
                "carbohydrate_g": "32",
                "fat_g": "4",
                "source": "meal_plan",
            }
        ],
        **overrides,
    }


def test_meal_plan_request_requires_meals_inside_a_bounded_date_range():
    payload = {
        "user_id": 7,
        "target_snapshot_id": 3,
        "start_date": "2026-09-22",
        "end_date": "2026-09-22",
        "planned_meals": [planned_meal()],
    }

    plan = MealPlanCreateRequest(**payload)

    assert plan.planned_meals[0].calorie_target_kcal == Decimal(500)
    with pytest.raises(ValueError, match="within the plan date range"):
        MealPlanCreateRequest(
            **{**payload, "planned_meals": [planned_meal(planned_date="2026-09-23")]}
        )


def test_meal_plan_generation_request_requires_unique_meal_types():
    with pytest.raises(ValueError, match="unique"):
        MealPlanGenerateRequest(
            user_id=7,
            start_date="2026-09-22",
            end_date="2026-09-22",
            meal_types=["breakfast", "breakfast"],
        )


@pytest.mark.asyncio
async def test_profile_save_clears_unsupported_dietary_values():
    db = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.one.return_value = {"user_id": 7}
    db.execute.return_value = result
    repo = NutritionRepository(db)

    await repo.upsert_profile(
        7,
        {
            "sex_for_energy_equation": "female",
            "activity_level": "moderate",
            "nutrition_goal": "maintenance",
            "allergies": ["milk"],
            "dietary_preferences": ["vegan"],
            "dietary_restrictions": ["gluten_free"],
        },
    )

    _, values = db.execute.await_args.args
    assert values["dietary_preferences"] == "[]"
    assert values["dietary_restrictions"] == "[]"


@pytest.mark.asyncio
async def test_generate_meal_plan_uses_active_target_and_safe_catalogue_foods():
    service = NutritionService(AsyncMock())
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
    service.repo.get_profile = AsyncMock(
        return_value={"allergies": ["milk"], "dietary_preferences": [], "dietary_restrictions": []}
    )
    service.repo.list_food_catalogue = AsyncMock(
        return_value=[
            {"id": 10, "description": "Milk", "calories_per_100g": Decimal(60), "protein_g_per_100g": Decimal(3), "carbohydrate_g_per_100g": Decimal(5), "fat_g_per_100g": Decimal(3), "fiber_g_per_100g": Decimal(0)},
            {"id": 11, "description": "Oats", "calories_per_100g": Decimal(400), "protein_g_per_100g": Decimal(10), "carbohydrate_g_per_100g": Decimal(70), "fat_g_per_100g": Decimal(8), "fiber_g_per_100g": Decimal(10)},
        ]
    )
    service.repo.get_food_safety_metadata = AsyncMock(
        return_value={
            10: {"id": 10, "allergen_status": "known", "allergen_data": {"contains": ["milk"]}},
            11: {"id": 11, "allergen_status": "known", "allergen_data": {"contains": []}},
        }
    )
    service.repo.get_target_snapshot = AsyncMock(return_value={"id": 3})
    service.repo.create_meal_plan = AsyncMock(return_value={"id": 41, "status": "draft"})

    result = await service.generate_meal_plan(
        7,
        MealPlanGenerateRequest(
            user_id=7,
            start_date="2026-09-22",
            end_date="2026-09-22",
            meal_types=["breakfast", "dinner"],
        ),
    )

    assert result == {"id": 41, "status": "draft"}
    create_args = service.repo.create_meal_plan.await_args.kwargs
    assert create_args["target_snapshot_id"] == 3
    assert create_args["generated_plan"]["generator"] == "deterministic_catalogue_v1"
    assert len(create_args["planned_meals"]) == 2
    assert {meal["items"][0]["food_name"] for meal in create_args["planned_meals"]} == {"Oats"}
    assert create_args["planned_meals"][0]["calorie_target_kcal"] == Decimal(900)


@pytest.mark.asyncio
async def test_generate_meal_plan_allows_unknown_allergens_without_saved_allergies():
    service = NutritionService(AsyncMock())
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
    service.repo.get_profile = AsyncMock(
        return_value={
            "allergies": [],
            "dietary_preferences": ["vegan"],
            "dietary_restrictions": ["gluten_free"],
        }
    )
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
        return_value={11: {"id": 11, "allergen_status": "unknown", "allergen_data": None}}
    )
    service.repo.get_target_snapshot = AsyncMock(return_value={"id": 3})
    service.repo.create_meal_plan = AsyncMock(return_value={"id": 41, "status": "draft"})

    await service.generate_meal_plan(
        7,
        MealPlanGenerateRequest(
            user_id=7,
            start_date="2026-09-22",
            end_date="2026-09-22",
            meal_types=["breakfast"],
        ),
    )

    create_args = service.repo.create_meal_plan.await_args.kwargs
    assert create_args["planned_meals"][0]["safety_status"] == "review_required"
    assert create_args["safety_warnings"] == [
        "Oats: allergen metadata is unknown; review required."
    ]


@pytest.mark.asyncio
async def test_generate_meal_plan_rejects_unknown_allergens_with_saved_allergies():
    service = NutritionService(AsyncMock())
    service.repo.get_active_target = AsyncMock(return_value={"id": 3})
    service.repo.get_profile = AsyncMock(return_value={"allergies": ["milk"]})
    service.repo.list_food_catalogue = AsyncMock(
        return_value=[{"id": 11, "description": "Oats", "calories_per_100g": Decimal(400)}]
    )
    service.repo.get_food_safety_metadata = AsyncMock(
        return_value={11: {"id": 11, "allergen_status": "unknown", "allergen_data": None}}
    )

    with pytest.raises(NutritionProfileIncompleteError, match="no safe foods"):
        await service.generate_meal_plan(
            7,
            MealPlanGenerateRequest(
                user_id=7,
                start_date="2026-09-22",
                end_date="2026-09-22",
                meal_types=["breakfast"],
            ),
        )


@pytest.mark.asyncio
async def test_generate_meal_plan_requires_active_targets_and_a_safe_catalogue():
    service = NutritionService(AsyncMock())
    service.repo.get_active_target = AsyncMock(return_value=None)
    request = MealPlanGenerateRequest(
        user_id=7,
        start_date="2026-09-22",
        end_date="2026-09-22",
        meal_types=["breakfast"],
    )
    with pytest.raises(NutritionProfileIncompleteError, match="Active nutrition targets"):
        await service.generate_meal_plan(7, request)

    service.repo.get_active_target.return_value = {"id": 3}
    service.repo.get_profile = AsyncMock(
        return_value={"allergies": [], "dietary_preferences": [], "dietary_restrictions": []}
    )
    service.repo.list_food_catalogue = AsyncMock(return_value=[])
    service.repo.get_food_safety_metadata = AsyncMock(return_value={})
    with pytest.raises(NutritionProfileIncompleteError, match="no safe foods"):
        await service.generate_meal_plan(7, request)


@pytest.mark.asyncio
async def test_create_meal_plan_serializes_version_allocation_and_persists_meals():
    db = AsyncMock()
    version_result = MagicMock()
    version_result.scalar_one.return_value = 2
    plan_result = MagicMock()
    plan_result.mappings.return_value.one.return_value = {"id": 41, "version": 2}
    db.execute.side_effect = [AsyncMock(), version_result, plan_result, AsyncMock()]
    repo = NutritionRepository(db)
    meal = planned_meal()

    result = await repo.create_meal_plan(
        user_id=7,
        target_snapshot_id=3,
        start_date=date(2026, 9, 22),
        end_date=date(2026, 9, 22),
        generated_plan={"strategy": "balanced"},
        safety_warnings=["Allergen metadata requires review."],
        planned_meals=[
            {
                **meal,
                "planned_date": date(2026, 9, 22),
                "calorie_target_kcal": Decimal(500),
                "protein_target_g": Decimal(30),
                "carbohydrate_target_g": Decimal(50),
                "fat_target_g": Decimal(15),
                "fiber_target_g": Decimal(8),
            }
        ],
    )

    assert result == {"id": 41, "version": 2}
    assert db.execute.await_count == 4
    lock_statement, lock_values = db.execute.await_args_list[0].args
    assert "pg_advisory_xact_lock" in str(lock_statement)
    assert lock_values == {"user_id": 7}
    version_statement, _ = db.execute.await_args_list[1].args
    assert "COALESCE(MAX(version), 0) + 1" in str(version_statement)
    insert_statement, insert_values = db.execute.await_args_list[2].args
    assert "INSERT INTO systemdb.nutrition_meal_plans" in str(insert_statement)
    assert "'draft'" in str(insert_statement)
    assert insert_values["version"] == 2
    assert insert_values["target_snapshot_id"] == 3


@pytest.mark.asyncio
async def test_get_active_meal_plan_scopes_query_to_user_and_requested_date():
    db = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = {"id": 41, "planned_meals": []}
    db.execute.return_value = result

    plan = await NutritionRepository(db).get_active_meal_plan(7, date(2026, 9, 22))

    assert plan == {"id": 41, "planned_meals": []}
    statement, values = db.execute.await_args.args
    assert "p.user_id = :user_id" in str(statement)
    assert "p.start_date <= :for_date" in str(statement)
    assert values == {"user_id": 7, "for_date": date(2026, 9, 22)}


@pytest.mark.asyncio
async def test_create_meal_plan_requires_a_target_snapshot_owned_by_the_user():
    service = NutritionService(AsyncMock())
    service.repo.get_target_snapshot = AsyncMock(return_value=None)
    service.repo.create_meal_plan = AsyncMock()
    payload = MealPlanCreateRequest(
        user_id=7,
        target_snapshot_id=3,
        start_date=date(2026, 9, 22),
        end_date=date(2026, 9, 22),
        planned_meals=[planned_meal()],
    )

    with pytest.raises(NutritionNotFoundError, match="target snapshot not found"):
        await service.create_meal_plan(7, payload)

    service.repo.create_meal_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_meal_plan_blocks_confirmed_allergen_conflicts():
    service = NutritionService(AsyncMock())
    service.repo.get_target_snapshot = AsyncMock(return_value={"id": 3})
    service.repo.get_profile = AsyncMock(
        return_value={"allergies": ["milk"], "dietary_restrictions": []}
    )
    service.repo.get_food_safety_metadata = AsyncMock(
        return_value={
            12: {
                "id": 12,
                "allergen_status": "known",
                "allergen_data": {"contains": ["milk"]},
            }
        }
    )
    service.repo.create_meal_plan = AsyncMock()
    payload = MealPlanCreateRequest(
        user_id=7,
        target_snapshot_id=3,
        start_date=date(2026, 9, 22),
        end_date=date(2026, 9, 22),
        planned_meals=[
            planned_meal(items=[{**planned_meal()["items"][0], "food_cache_id": 12}])
        ],
    )

    with pytest.raises(NutritionMealPlanSafetyError, match="confirmed allergies"):
        await service.create_meal_plan(7, payload)

    service.repo.create_meal_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_meal_plan_persists_server_computed_safety_results():
    service = NutritionService(AsyncMock())
    service.repo.get_target_snapshot = AsyncMock(return_value={"id": 3})
    service.repo.get_profile = AsyncMock(
        return_value={"allergies": [], "dietary_restrictions": []}
    )
    service.repo.get_food_safety_metadata = AsyncMock(
        return_value={
            12: {
                "id": 12,
                "allergen_status": "known",
                "allergen_data": {"contains": ["milk"]},
            }
        }
    )
    service.repo.create_meal_plan = AsyncMock(return_value={"id": 41})
    payload = MealPlanCreateRequest(
        user_id=7,
        target_snapshot_id=3,
        start_date=date(2026, 9, 22),
        end_date=date(2026, 9, 22),
        safety_warnings=["Untrusted caller warning"],
        planned_meals=[
            planned_meal(items=[{**planned_meal()["items"][0], "food_cache_id": 12}])
        ],
    )

    assert await service.create_meal_plan(7, payload) == {"id": 41}
    values = service.repo.create_meal_plan.await_args.kwargs
    assert values["safety_warnings"] == []
    assert values["planned_meals"][0]["safety_status"] == "safe"
    assert values["planned_meals"][0]["safety_warnings"] == []


@pytest.mark.asyncio
async def test_confirm_meal_plan_reassesses_draft_and_supersedes_atomically():
    service = NutritionService(AsyncMock())
    service.repo.lock_user_meal_plans = AsyncMock()
    plan = {
        "id": 41,
        "status": "draft",
        "start_date": date(2026, 9, 22),
        "end_date": date(2026, 9, 22),
        "planned_meals": [
            {
                "id": 9,
                "planned_date": date(2026, 9, 22),
                "items": [{"food_cache_id": 12, "food_name": "Oats"}],
            }
        ],
    }
    service.repo.get_meal_plan = AsyncMock(return_value=plan)
    service.repo.get_profile = AsyncMock(
        return_value={"allergies": [], "dietary_restrictions": []}
    )
    service.repo.get_food_safety_metadata = AsyncMock(
        return_value={
            12: {
                "id": 12,
                "allergen_status": "known",
                "allergen_data": {"contains": []},
            }
        }
    )
    service.repo.activate_draft_meal_plan = AsyncMock(
        return_value={"id": 41, "status": "active"}
    )

    assert await service.confirm_meal_plan(7, 41) == {"id": 41, "status": "active"}
    service.repo.lock_user_meal_plans.assert_awaited_once_with(7)
    service.repo.activate_draft_meal_plan.assert_awaited_once()
    args = service.repo.activate_draft_meal_plan.await_args.args
    assert args[:4] == (7, 41, date(2026, 9, 22), date(2026, 9, 22))
    assert args[4][0]["safety_status"] == "safe"


@pytest.mark.asyncio
async def test_confirm_rejects_non_draft_and_newly_blocked_safety_results():
    service = NutritionService(AsyncMock())
    service.repo.lock_user_meal_plans = AsyncMock()
    service.repo.activate_draft_meal_plan = AsyncMock()
    service.repo.get_meal_plan = AsyncMock(
        return_value={"id": 41, "status": "active", "planned_meals": []}
    )
    with pytest.raises(NutritionMealPlanTransitionError, match="Only draft"):
        await service.confirm_meal_plan(7, 41)

    service.repo.get_meal_plan.return_value = {
        "id": 41,
        "status": "draft",
        "planned_meals": [
            {"id": 9, "items": [{"food_cache_id": 12, "food_name": "Milk"}]}
        ],
    }
    service.repo.get_profile = AsyncMock(
        return_value={"allergies": ["milk"], "dietary_restrictions": []}
    )
    service.repo.get_food_safety_metadata = AsyncMock(
        return_value={
            12: {
                "id": 12,
                "allergen_status": "known",
                "allergen_data": {"contains": ["milk"]},
            }
        }
    )
    with pytest.raises(NutritionMealPlanSafetyError, match="confirmed allergies"):
        await service.confirm_meal_plan(7, 41)
    service.repo.activate_draft_meal_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_archive_only_allows_drafts_or_active_plans_and_uses_ownership_lookup():
    service = NutritionService(AsyncMock())
    service.repo.lock_user_meal_plans = AsyncMock()
    service.repo.get_meal_plan = AsyncMock(return_value=None)
    with pytest.raises(NutritionNotFoundError, match="Meal plan not found"):
        await service.archive_meal_plan(7, 99)
    service.repo.get_meal_plan.return_value = {"id": 41, "status": "superseded"}
    with pytest.raises(NutritionMealPlanTransitionError, match="draft or active"):
        await service.archive_meal_plan(7, 41)
    service.repo.get_meal_plan.return_value = {"id": 41, "status": "active"}
    service.repo.archive_meal_plan = AsyncMock(
        return_value={"id": 41, "status": "archived"}
    )
    assert await service.archive_meal_plan(7, 41) == {"id": 41, "status": "archived"}
    service.repo.archive_meal_plan.assert_awaited_once_with(7, 41)


@pytest.mark.asyncio
async def test_nutrition_context_is_scoped_to_the_requested_user_and_date():
    service = NutritionService(AsyncMock())
    service.repo.get_target_for_date = AsyncMock(return_value={"id": 3})
    service.repo.get_active_meal_plan = AsyncMock(return_value={"id": 41})
    for_date = date(2026, 9, 22)

    context = await service.get_nutrition_context(7, for_date)

    assert context == {
        "date": for_date,
        "target_snapshot": {"id": 3},
        "meal_plan": {"id": 41},
    }
    service.repo.get_target_for_date.assert_awaited_once_with(7, for_date)
    service.repo.get_active_meal_plan.assert_awaited_once_with(7, for_date)
