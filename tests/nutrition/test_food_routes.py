"""Public and private Nutrition food-route contract coverage."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.api.routes.auth import get_current_user
from app.api.routes.nutrition import router
from app.services.nutrition_agent_client import nutrition_agent_client
from services.nutrition_agent.app import main as nutrition_main


@pytest.fixture
def public_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": 42}
    return app


@pytest.mark.asyncio
async def test_public_food_search_forwards_only_contract_parameters(
    monkeypatch: pytest.MonkeyPatch, public_app: FastAPI
) -> None:
    captured: dict[str, object] = {}

    async def request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured.update(method=method, path=path, **kwargs)
        return {"items": [], "source": "cache_only", "upstream_status": "not_requested", "stale": False}

    monkeypatch.setattr(nutrition_agent_client, "request", request)
    transport = httpx.ASGITransport(app=public_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/nutrition/foods", params={"q": " chicken ", "limit": 7, "include_usda": "false"})

    assert response.status_code == 200
    assert captured == {
        "method": "GET",
        "path": "/v1/nutrition/foods",
        "params": {"q": "chicken", "limit": 7, "include_usda": False},
    }


@pytest.mark.asyncio
async def test_public_food_detail_is_authenticated_and_not_user_scoped(
    monkeypatch: pytest.MonkeyPatch, public_app: FastAPI
) -> None:
    captured: dict[str, object] = {}

    async def request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured.update(method=method, path=path, **kwargs)
        return {"fdc_id": 123, "name": "Chicken"}

    monkeypatch.setattr(nutrition_agent_client, "request", request)
    transport = httpx.ASGITransport(app=public_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/nutrition/foods/123")

    assert response.status_code == 200
    assert captured == {"method": "GET", "path": "/v1/nutrition/foods/123"}


@pytest.mark.asyncio
async def test_private_food_search_uses_contract_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def search_food_cache(query: str, limit: int) -> list[dict[str, object]]:
        captured.update(query=query, limit=limit)
        return []

    monkeypatch.setattr(nutrition_main.repository, "search_food_cache", search_food_cache)
    response = await nutrition_main.search_foods(q=" oats ", limit=20, include_usda=False)

    assert captured == {"query": "oats", "limit": 20}
    assert response.source == "cache_only"
    assert response.upstream_status == "not_requested"