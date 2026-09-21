from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import get_current_user
from app.api.routes.nutrition import get_nutrition_service, router
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


def test_food_catalogue_uses_authenticated_user_and_capped_limit(nutrition_client):
    client, service = nutrition_client
    service.get_food_catalogue.return_value = [{"id": 1, "description": "Oats"}]

    response = client.post("/api/nutrition/foods/catalogue", json={"limit": 200})

    assert response.status_code == 200
    assert response.json() == {"items": [{"id": 1, "description": "Oats"}]}
    service.get_food_catalogue.assert_awaited_once_with(9, 200)


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
