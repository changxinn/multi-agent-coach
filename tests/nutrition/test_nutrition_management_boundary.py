"""Boundary tests for direct, POST-only Nutrition Management operations."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.api.routes.auth import get_current_user
from app.api.routes.nutrition_management import router
from app.db.database import get_db
from app.services.nutrition_management_service import NutritionManagementNotFound


@pytest.fixture
def management_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": 42}
    app.dependency_overrides[get_db] = lambda: object()
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_management_routes_are_post_only_and_reject_user_id(management_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=management_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        get_response = await client.get("/api/nutrition-management/profile/get")
        invalid_response = await client.post(
            "/api/nutrition-management/profile/save",
            json={"user_id": 999, "timezone": "Asia/Singapore"},
        )

    assert get_response.status_code == 405
    assert invalid_response.status_code == 422


@pytest.mark.asyncio
async def test_management_resource_ownership_uses_the_same_not_found_response(
    management_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def missing(*_: object, **__: object) -> dict[str, object]:
        raise NutritionManagementNotFound

    monkeypatch.setattr(
        "app.api.routes.nutrition_management.NutritionManagementService.meal", missing
    )
    transport = httpx.ASGITransport(app=management_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/nutrition-management/meals/get", json={"id": 8})

    assert response.status_code == 404
    assert response.json()["detail"] == {"code": "MEAL_LOG_NOT_FOUND"}


@pytest.mark.asyncio
async def test_assessment_list_returns_only_the_safe_projection(
    management_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def assessments(*_: object, **__: object) -> dict[str, object]:
        return {
            "items": [{"id": 1, "status": "green", "score": 0, "tdee": 2100,
                       "macro_targets": {}, "message": "Safe", "recommendations": [],
                       "safety_findings": [], "policy_version": "nutrition-safety-v1",
                       "created_at": "2026-01-01T00:00:00Z"}],
            "limit": 20, "offset": 0, "total": 1,
        }

    monkeypatch.setattr(
        "app.api.routes.nutrition_management.NutritionManagementService.assessments", assessments
    )
    transport = httpx.ASGITransport(app=management_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/nutrition-management/assessments/list", json={})

    assert response.status_code == 200
    assert "tool_trace" not in response.text
    assert "response" not in response.text