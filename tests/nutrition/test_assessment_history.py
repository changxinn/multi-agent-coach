"""Privacy-safe Nutrition assessment-history repository and route coverage."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI

from app.api.routes.auth import get_current_user
from app.api.routes.nutrition import router
from app.services.nutrition_agent_client import nutrition_agent_client
from services.nutrition_agent.app import main as nutrition_main
from services.nutrition_agent.app.repository import NutritionRepository


class _Settings:
    @staticmethod
    def validated_schema() -> str:
        return "systemdb"


class _HistoryPool:
    def __init__(self) -> None:
        self.fetch_query = ""
        self.fetch_arguments: tuple[object, ...] = ()
        self.count_query = ""

    async def fetch(self, query: str, *arguments: object) -> list[dict[str, object]]:
        self.fetch_query = query
        self.fetch_arguments = arguments
        return [{
            "id": 9, "status": "escalate", "score": 10, "tdee": None,
            "macro_targets": None,
            "presentation_message": "Please seek qualified healthcare support.",
            "safety_projection": {
                "findings": [{"code": "DIABETES_OR_INSULIN", "severity": "escalate"}],
                "escalation": {"message": "Please seek qualified healthcare support.", "urgent": False},
            },
            "recommendations": ["Seek qualified healthcare support."],
            "policy_version": "nutrition-safety-v1",
            "created_at": datetime(2026, 9, 1, tzinfo=UTC),
        }]

    async def fetchval(self, query: str, *_: object) -> int:
        self.count_query = query
        return 1


@pytest.mark.asyncio
async def test_history_repository_reads_only_redacted_columns_and_scopes_page() -> None:
    repository = NutritionRepository(_Settings())
    pool = _HistoryPool()
    repository.pool = pool  # type: ignore[assignment]

    items, total = await repository.list_assessments(42, limit=7, offset=3)

    assert total == 1
    assert items[0].id == 9
    assert items[0].message == "Please seek qualified healthcare support."
    assert pool.fetch_arguments == (42, 7, 3)
    assert "WHERE user_id = $1" in pool.fetch_query
    assert "ORDER BY created_at DESC NULLS LAST, id DESC" in pool.fetch_query
    assert "response" not in pool.fetch_query.lower()
    assert "tool_trace" not in pool.fetch_query.lower()
    assert "trigger_codes" not in pool.fetch_query.lower()
    assert "WHERE user_id=$1" in pool.count_query


@pytest.mark.asyncio
async def test_private_history_route_returns_paginated_redacted_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def list_assessments(user_id: int, limit: int, offset: int) -> tuple[list[object], int]:
        captured.update(user_id=user_id, limit=limit, offset=offset)
        return [], 0

    monkeypatch.setattr(nutrition_main.repository, "list_assessments", list_assessments)
    response = await nutrition_main.assessment_history(77, limit=5, offset=2)

    assert captured == {"user_id": 77, "limit": 5, "offset": 2}
    assert response == {"items": [], "limit": 5, "offset": 2, "total": 0}


@pytest.mark.asyncio
async def test_public_history_is_authenticated_user_scoped_and_preserves_redacted_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": 42}
    captured: dict[str, object] = {}
    raw_source = "I am taking an unlisted medication and need dosage advice"

    async def request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        captured.update(method=method, path=path, **kwargs)
        return {
            "items": [{"id": 9, "agent": "nutrition", "status": "escalate", "score": 10,
                "message": "Please seek qualified healthcare support.",
                "recommendations": ["Seek qualified healthcare support."], "tdee": None,
                "macro_targets": None, "safety_findings": [], "escalation": None,
                "policy_version": "nutrition-safety-v1", "created_at": "2026-09-01T00:00:00Z"}],
            "limit": 5, "offset": 2, "total": 1,
        }

    monkeypatch.setattr(nutrition_agent_client, "request", request)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/nutrition/assessment-history", params={"limit": 5, "offset": 2})

    assert response.status_code == 200
    assert captured == {"method": "GET", "path": "/v1/nutrition/users/42/assessment-history", "json": None, "params": {"limit": 5, "offset": 2}}
    body = response.json()
    assert raw_source not in str(body)
    assert "medical_conditions" not in str(body)
    assert "tool_trace" not in str(body)