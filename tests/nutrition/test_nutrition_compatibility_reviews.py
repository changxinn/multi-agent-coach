from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import get_current_user
from app.api.routes.nutrition import (
    get_nutrition_service,
    require_compatibility_reviewer,
    router,
)
from app.services.nutrition_agent_client import (
    NutritionAgentUnavailableError,
    NutritionCompatibilityReviewError,
)
from app.services.nutrition_service import (
    NutritionNotFoundError as MainNutritionNotFoundError,
)
from services.nutrition_agent.app.food_compatibility_policy import validate_human_review
from services.nutrition_agent.app.repository import NutritionRepository
from services.nutrition_agent.app.service import (
    NutritionNotFoundError,
    NutritionService,
)


@pytest.fixture
def compatibility_client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    service = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 44,
        "email": "nutrition.admin@example.com",
    }
    app.dependency_overrides[require_compatibility_reviewer] = lambda: {
        "id": 44,
        "email": "nutrition.admin@example.com",
    }
    app.dependency_overrides[get_nutrition_service] = lambda: service
    with TestClient(app) as client:
        yield client, service


def review_payload(**overrides):
    payload = {
        "food_cache_id": 12,
        "review_status": "approved",
        "allergen_status": "known",
        "known_allergens": ["Milk protein"],
        "strict_suitability": {
            "vegetarian": "suitable",
            "vegan": "unsuitable",
            "pescatarian": "suitable",
            "halal": "suitable",
            "kosher": "suitable",
            "gluten_free": "suitable",
            "dairy_free": "unsuitable",
            "egg_free": "suitable",
            "soy_free": "suitable",
            "nut_free": "suitable",
            "no_pork": "suitable",
            "no_beef": "suitable",
            "alcohol_free": "suitable",
        },
        "evidence": {"source": "manufacturer label"},
        "confidence": "0.95",
        "policy_version": "compatibility_review_v1",
    }
    payload.update(overrides)
    return payload


def test_gateway_forwards_authenticated_reviewer_identity_only(compatibility_client):
    client, service = compatibility_client
    service.review_food_compatibility.return_value = {
        "food_cache_id": 12,
        "review_status": "approved",
    }

    response = client.post("/api/nutrition/compatibility/review", json=review_payload())

    assert response.status_code == 200
    service.review_food_compatibility.assert_awaited_once()
    _, kwargs = service.review_food_compatibility.await_args
    assert kwargs == {
        "reviewer_user_id": 44,
        "reviewer_email": "nutrition.admin@example.com",
    }


def test_gateway_rejects_browser_supplied_reviewer_identity(compatibility_client):
    client, service = compatibility_client

    response = client.post(
        "/api/nutrition/compatibility/review",
        json=review_payload(reviewer_email="forged@example.com"),
    )

    assert response.status_code == 422
    service.review_food_compatibility.assert_not_awaited()


def test_gateway_returns_queue_pagination_metadata(compatibility_client):
    client, service = compatibility_client
    service.get_compatibility_review_queue.return_value = {
        "items": [{"food_cache_id": 12, "description": "Review oats"}],
        "total": 12613,
        "offset": 25,
        "limit": 25,
    }

    response = client.post(
        "/api/nutrition/compatibility/review-queue",
        json={"query": "oats", "offset": 25, "limit": 25},
    )

    assert response.status_code == 200
    assert response.json() == service.get_compatibility_review_queue.return_value
    assert service.get_compatibility_review_queue.await_args.args[0].query == "oats"


@pytest.mark.parametrize(
    ("path", "method", "error", "expected_status"),
    [
        (
            "/api/nutrition/compatibility/review-queue",
            "get_compatibility_review_queue",
            NutritionAgentUnavailableError("offline"),
            503,
        ),
        (
            "/api/nutrition/compatibility/review-detail",
            "get_compatibility_review_detail",
            MainNutritionNotFoundError("missing"),
            404,
        ),
        (
            "/api/nutrition/compatibility/review-history",
            "get_compatibility_review_history",
            NutritionAgentUnavailableError("offline"),
            503,
        ),
        (
            "/api/nutrition/compatibility/review",
            "review_food_compatibility",
            NutritionCompatibilityReviewError("invalid review"),
            422,
        ),
    ],
)
def test_gateway_maps_compatibility_review_service_errors(
    compatibility_client, path, method, error, expected_status
):
    client, service = compatibility_client
    getattr(service, method).side_effect = error
    payload = (
        review_payload()
        if path.endswith("/review")
        else {}
        if path.endswith("review-queue")
        else {"food_cache_id": 12}
    )

    response = client.post(path, json=payload)

    assert response.status_code == expected_status
    assert response.json()["detail"] == str(error)


@pytest.mark.asyncio
async def test_review_queue_orders_food_names_case_insensitively_ascending():
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 2
    rows_result = MagicMock()
    rows_result.mappings.return_value.all.return_value = [
        {"food_cache_id": 2, "description": "Apple"},
        {"food_cache_id": 1, "description": "banana"},
    ]
    db.execute.side_effect = [count_result, rows_result]

    queue = await NutritionRepository(db).list_compatibility_review_queue(
        statuses=["review_required"], query=" fruit ", offset=25, limit=25
    )

    statement, parameters = db.execute.await_args_list[1].args
    sql = str(statement)
    assert "ORDER BY LOWER(f.description) ASC, f.id ASC" in sql
    assert "c.updated_at DESC" not in sql
    assert parameters == {
        "statuses": ["review_required"],
        "query": "fruit",
        "offset": 25,
        "limit": 25,
    }
    assert queue == {
        "items": [
            {"food_cache_id": 2, "description": "Apple"},
            {"food_cache_id": 1, "description": "banana"},
        ],
        "total": 2,
        "offset": 25,
        "limit": 25,
    }


@pytest.mark.asyncio
async def test_review_queue_omits_search_parameter_for_blank_query():
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    rows_result = MagicMock()
    rows_result.mappings.return_value.all.return_value = []
    db.execute.side_effect = [count_result, rows_result]

    assert await NutritionRepository(db).list_compatibility_review_queue(
        statuses=["pending"], query="   ", offset=0, limit=25
    ) == {"items": [], "total": 0, "offset": 0, "limit": 25}
    assert db.execute.await_args.args[1] == {
        "statuses": ["pending"],
        "offset": 0,
        "limit": 25,
    }


@pytest.mark.asyncio
async def test_repository_returns_detail_history_and_persists_review_audit_record():
    db = AsyncMock()
    existing_result = MagicMock()
    existing_result.mappings.return_value.first.return_value = {
        "food_cache_id": 12,
        "review_status": "pending",
    }
    updated_result = MagicMock()
    updated_result.mappings.return_value.first.return_value = {
        "food_cache_id": 12,
        "review_status": "approved",
    }
    db.execute.side_effect = [existing_result, MagicMock(), MagicMock(), updated_result]
    payload = {
        **review_payload(),
        "classifier_version": None,
        "review_note": None,
        "reviewer_user_id": 44,
        "reviewer_email": "admin@example.com",
    }

    result = await NutritionRepository(db).review_food_compatibility(payload)

    assert result == {"food_cache_id": 12, "review_status": "approved"}
    update_parameters = db.execute.await_args_list[1].args[1]
    history_parameters = db.execute.await_args_list[2].args[1]
    assert update_parameters["known_allergens"] == '["Milk protein"]'
    assert history_parameters["prior_review_status"] == "pending"
    assert '"allergen_status": "known"' in history_parameters["metadata"]


@pytest.mark.asyncio
async def test_service_compatibility_review_operations_delegate_and_map_missing_records():
    repo = AsyncMock()
    service = NutritionService(AsyncMock())
    service.repo = repo
    queue_payload = MagicMock(statuses=["pending"], query=None, offset=0, limit=25)
    detail = {"food_cache_id": 12}
    repo.list_compatibility_review_queue.return_value = {"items": []}
    repo.get_compatibility_review_detail.return_value = detail
    repo.list_compatibility_review_history.return_value = [{"id": 1}]
    payload = MagicMock()
    payload.model_dump.return_value = {
        **review_payload(),
        "classifier_version": None,
        "review_note": None,
    }
    repo.review_food_compatibility.return_value = detail

    assert await service.get_compatibility_review_queue(queue_payload) == {"items": []}
    assert await service.get_compatibility_review_detail(12) == detail
    assert await service.get_compatibility_review_history(12) == [{"id": 1}]
    assert await service.review_food_compatibility(payload) == detail
    assert repo.review_food_compatibility.await_args.args[0]["known_allergens"] == [
        "milk_protein"
    ]

    repo.get_compatibility_review_detail.return_value = None
    with pytest.raises(NutritionNotFoundError, match="Food compatibility record"):
        await service.get_compatibility_review_detail(99)
    repo.review_food_compatibility.return_value = None
    with pytest.raises(NutritionNotFoundError, match="Food compatibility record"):
        await service.review_food_compatibility(payload)


def test_gateway_review_routes_require_reviewer_dependency():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": 1,
        "email": "member@example.com",
    }
    with TestClient(app) as client:
        response = client.post("/api/nutrition/compatibility/review-queue", json={})

    assert response.status_code == 403


def test_approved_review_requires_complete_safety_metadata():
    with pytest.raises(ValueError, match="known allergen"):
        validate_human_review(
            review_status="approved",
            allergen_status="unknown",
            known_allergens=[],
            strict_suitability={},
            evidence={},
            confidence=None,
        )


def test_non_approved_review_stays_permissive_and_normalizes_allergens():
    assert validate_human_review(
        review_status="review_required",
        allergen_status="unknown",
        known_allergens=["Milk Protein"],
        strict_suitability={},
        evidence={},
        confidence=None,
    ) == ["milk_protein"]
