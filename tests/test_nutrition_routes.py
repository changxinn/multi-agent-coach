from datetime import date
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import get_current_user
from app.api.routes.nutrition import get_nutrition_service, router
from app.services.nutrition_agent_client import (
    NutritionAgentUnavailableError,
    NutritionMealPlanValidationError,
)
from app.services.nutrition_service import (
    NutritionFoodDataError,
    NutritionNotFoundError,
)


@pytest.fixture
def nutrition_client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    service = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: {"id": 9, "role": "user"}
    app.dependency_overrides[get_nutrition_service] = lambda: service
    with TestClient(app) as client:
        yield client, service


def meal_payload(**overrides):
    return {
        "eaten_at": "2026-09-20T12:00:00Z",
        "meal_type": "lunch",
        "items": [
            {
                "food_name": "Rice",
                "quantity": 1,
                "unit": "bowl",
                "calories": 200,
                "protein_g": 0,
                "carbohydrate_g": 0,
                "fat_g": 0,
            }
        ],
        **overrides,
    }


def meal_plan_payload(**overrides):
    return {
        "target_snapshot_id": 3,
        "start_date": "2026-09-22",
        "end_date": "2026-09-22",
        "planned_meals": [
            {
                "planned_date": "2026-09-22",
                "meal_type": "breakfast",
                "calorie_target_kcal": 500,
                "protein_target_g": 30,
                "carbohydrate_target_g": 50,
                "fat_target_g": 15,
                "fiber_target_g": 8,
                "items": [
                    {
                        "food_name": "Oats",
                        "quantity": 50,
                        "unit": "g",
                        "calories": 190,
                        "source": "meal_plan",
                    }
                ],
            }
        ],
        **overrides,
    }


def test_create_meal_plan_scopes_to_user_and_forwards_idempotency_key(nutrition_client):
    client, service = nutrition_client
    service.create_meal_plan.return_value = {"id": 41, "version": 1}

    response = client.post(
        "/api/nutrition/meal-plans/create",
        json=meal_plan_payload(),
        headers={"Idempotency-Key": "plan-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"id": 41, "version": 1}
    assert service.create_meal_plan.await_args.args[0] == 9
    assert service.create_meal_plan.await_args.args[1].target_snapshot_id == 3
    assert service.create_meal_plan.await_args.args[2] == "plan-1"


def test_generate_meal_plan_scopes_to_user_and_forwards_idempotency_key(nutrition_client):
    client, service = nutrition_client
    service.generate_meal_plan.return_value = {"id": 42, "status": "draft"}

    response = client.post(
        "/api/nutrition/meal-plans/generate",
        json={
            "start_date": "2026-09-22",
            "end_date": "2026-09-22",
            "meal_types": ["breakfast", "lunch"],
        },
        headers={"Idempotency-Key": "generate-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"id": 42, "status": "draft"}
    assert service.generate_meal_plan.await_args.args[0] == 9
    assert service.generate_meal_plan.await_args.args[1].meal_types == ["breakfast", "lunch"]
    assert service.generate_meal_plan.await_args.args[2] == "generate-1"


def test_profile_save_rejects_unsupported_dietary_fields(nutrition_client):
    client, service = nutrition_client

    response = client.post(
        "/api/nutrition/profile/save",
        json={
            "sex_for_energy_equation": "female",
            "activity_level": "moderate",
            "nutrition_goal": "maintenance",
            "allergies": [],
            "dietary_preferences": ["vegan"],
        },
    )

    assert response.status_code == 422
    service.update_profile.assert_not_awaited()


def test_meal_plan_active_and_context_scope_date_to_authenticated_user(
    nutrition_client,
):
    client, service = nutrition_client
    service.get_active_meal_plan.return_value = {"id": 41}
    service.get_nutrition_context.return_value = {
        "date": "2026-09-22",
        "meal_plan": {"id": 41},
    }

    active = client.post(
        "/api/nutrition/meal-plans/active", json={"date": "2026-09-22"}
    )
    context = client.post("/api/nutrition/context", json={"date": "2026-09-22"})

    assert active.json() == {"meal_plan": {"id": 41}}
    service.get_active_meal_plan.assert_awaited_once_with(9, date(2026, 9, 22))
    assert context.json()["meal_plan"] == {"id": 41}
    service.get_nutrition_context.assert_awaited_once_with(9, date(2026, 9, 22))


def test_meal_plan_lifecycle_routes_scope_plan_ids_and_forward_idempotency(
    nutrition_client,
):
    client, service = nutrition_client
    service.get_meal_plan.return_value = {"id": 41, "status": "draft"}
    service.list_meal_plans.return_value = [{"id": 41}]
    service.confirm_meal_plan.return_value = {"id": 41, "status": "active"}
    service.archive_meal_plan.return_value = {"id": 41, "status": "archived"}

    assert (
        client.post("/api/nutrition/meal-plans/get", json={"meal_plan_id": 41}).json()[
            "id"
        ]
        == 41
    )
    assert client.post("/api/nutrition/meal-plans/list", json={}).json() == {
        "items": [{"id": 41}]
    }
    assert (
        client.post(
            "/api/nutrition/meal-plans/confirm",
            json={"meal_plan_id": 41},
            headers={"Idempotency-Key": "confirm-1"},
        ).json()["status"]
        == "active"
    )
    assert (
        client.post(
            "/api/nutrition/meal-plans/archive",
            json={"meal_plan_id": 41},
            headers={"Idempotency-Key": "archive-1"},
        ).json()["status"]
        == "archived"
    )
    service.get_meal_plan.assert_awaited_once_with(9, 41)
    service.list_meal_plans.assert_awaited_once_with(9)
    service.confirm_meal_plan.assert_awaited_once_with(9, 41, "confirm-1")
    service.archive_meal_plan.assert_awaited_once_with(9, 41, "archive-1")


@pytest.mark.parametrize(
    ("path", "service_method", "detail"),
    [
        (
            "/api/nutrition/meal-plans/confirm",
            "confirm_meal_plan",
            "Only draft meal plans can be confirmed",
        ),
        (
            "/api/nutrition/meal-plans/confirm",
            "confirm_meal_plan",
            "Meal plan is blocked by the user's allergen restrictions",
        ),
        (
            "/api/nutrition/meal-plans/archive",
            "archive_meal_plan",
            "Only draft or active meal plans can be archived",
        ),
    ],
)
def test_meal_plan_lifecycle_validation_errors_preserve_details(
    nutrition_client, path, service_method, detail
):
    client, service = nutrition_client
    getattr(service, service_method).side_effect = NutritionMealPlanValidationError(
        detail
    )

    response = client.post(
        path,
        json={"meal_plan_id": 41},
        headers={"Idempotency-Key": "lifecycle-1"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": detail}
    getattr(service, service_method).assert_awaited_once_with(9, 41, "lifecycle-1")


def test_meal_plan_agent_outage_returns_service_unavailable(nutrition_client):
    client, service = nutrition_client
    service.get_nutrition_context.side_effect = NutritionAgentUnavailableError(
        "Nutrition service is temporarily unavailable"
    )

    response = client.post("/api/nutrition/context", json={"date": "2026-09-22"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Nutrition service is temporarily unavailable"


def test_meal_plan_request_rejects_self_certified_safety_and_duplicate_meals(
    nutrition_client,
):
    client, _ = nutrition_client

    safe = client.post(
        "/api/nutrition/meal-plans/create",
        json=meal_plan_payload(
            planned_meals=[
                {**meal_plan_payload()["planned_meals"][0], "safety_status": "safe"}
            ]
        ),
    )
    duplicate = client.post(
        "/api/nutrition/meal-plans/create",
        json=meal_plan_payload(planned_meals=meal_plan_payload()["planned_meals"] * 2),
    )

    assert safe.status_code == 422
    assert duplicate.status_code == 422


def test_list_meals_uses_post_body_and_scopes_to_authenticated_user(nutrition_client):
    client, service = nutrition_client
    service.list_meals.return_value = []

    response = client.post("/api/nutrition/meals/list", json={"date": "2026-09-20"})

    assert response.status_code == 200
    assert response.json() == {"items": []}
    service.list_meals.assert_awaited_once()
    assert service.list_meals.await_args.args[0] == 9
    assert service.list_meals.await_args.args[1].isoformat() == "2026-09-20"


def test_replace_meal_preserves_not_found_contract(nutrition_client):
    client, service = nutrition_client
    service.replace_meal.side_effect = NutritionNotFoundError("Meal not found")

    response = client.post(
        "/api/nutrition/meals/replace", json=meal_payload(meal_id=99)
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Meal not found"
    assert service.replace_meal.await_args.args[:2] == (9, 99)


def test_delete_meal_returns_json_success_contract(nutrition_client):
    client, service = nutrition_client

    response = client.post("/api/nutrition/meals/delete", json={"meal_id": 99})

    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    service.delete_meal.assert_awaited_once_with(9, 99)


def test_food_search_translates_provider_failure_to_service_unavailable(
    nutrition_client,
):
    client, service = nutrition_client
    service.search_foods.side_effect = NutritionFoodDataError("USDA unavailable")

    response = client.post("/api/nutrition/foods/search", json={"query": "oats"})

    assert response.status_code == 503
    assert response.json()["detail"] == "USDA unavailable"


def test_food_catalogue_uses_authenticated_user_without_a_limit(nutrition_client):
    client, service = nutrition_client
    service.get_food_catalogue.return_value = [{"id": 1, "description": "Oats"}]

    response = client.post("/api/nutrition/foods/catalogue", json={})

    assert response.status_code == 200
    assert response.json() == {"items": [{"id": 1, "description": "Oats"}]}
    service.get_food_catalogue.assert_awaited_once_with(9)


def test_food_catalogue_rejects_legacy_limit_parameter(nutrition_client):
    client, service = nutrition_client

    response = client.post("/api/nutrition/foods/catalogue", json={"limit": 200})

    assert response.status_code == 422
    service.get_food_catalogue.assert_not_awaited()


def test_manual_meal_requires_explicit_macros(nutrition_client):
    client, _ = nutrition_client
    payload = meal_payload(
        items=[
            {
                "food_name": "Homemade soup",
                "quantity": 1,
                "unit": "bowl",
                "calories": 100,
            }
        ]
    )

    response = client.post("/api/nutrition/meals", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/nutrition/profile"),
        ("put", "/api/nutrition/profile"),
        ("get", "/api/nutrition/targets/active"),
        ("get", "/api/nutrition/foods/search"),
        ("get", "/api/nutrition/foods/123"),
        ("get", "/api/nutrition/meals"),
        ("put", "/api/nutrition/meals/99"),
        ("delete", "/api/nutrition/meals/99"),
        ("get", "/api/nutrition/daily-summary"),
        ("get", "/api/nutrition/adherence"),
    ],
)
def test_retired_nutrition_methods_return_method_not_allowed(
    nutrition_client, method, path
):
    client, _ = nutrition_client

    response = getattr(client, method)(path)

    assert response.status_code == 405


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/nutrition/profile/get", {"unexpected": True}),
        ("/api/nutrition/foods/search", {"query": "o"}),
        ("/api/nutrition/foods/detail", {}),
        ("/api/nutrition/meals/list", {}),
        ("/api/nutrition/meals/delete", {"meal_id": 0}),
        (
            "/api/nutrition/adherence",
            {"from_date": "2026-09-01", "to_date": "2026-10-03"},
        ),
    ],
)
def test_post_nutrition_requests_validate_json_bodies(nutrition_client, path, payload):
    client, _ = nutrition_client

    response = client.post(path, json=payload)

    assert response.status_code == 422
