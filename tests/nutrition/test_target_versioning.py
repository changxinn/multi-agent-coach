"""Regression coverage for immutable, date-effective Nutrition targets."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from fastapi import FastAPI

from app.api.routes.auth import get_current_user
from app.api.routes.nutrition import router
from app.services.nutrition_agent_client import nutrition_agent_client
from services.nutrition_agent.app.repository import NutritionRepository


class _Settings:
    @staticmethod
    def validated_schema() -> str:
        return "systemdb"


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> None:
        return None


class _Connection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.insert: tuple[str, tuple[object, ...]] | None = None

    def transaction(self) -> _Transaction:
        return _Transaction()

    async def execute(self, query: str, *arguments: object) -> None:
        self.executed.append((query, arguments))

    async def fetchrow(self, query: str, *arguments: object) -> dict[str, object]:
        self.insert = (query, arguments)
        return {"id": 9, "user_id": arguments[0], "version": 2}


class _Acquire:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _Connection:
        return self.connection

    async def __aexit__(self, *_: object) -> None:
        return None


class _Pool:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def acquire(self) -> _Acquire:
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_save_target_serializes_revisions_and_bounds_backfilled_interval() -> None:
    connection = _Connection()
    repository = NutritionRepository(_Settings())
    repository.pool = _Pool(connection)  # type: ignore[assignment]

    result = await repository.save_target(42, {"age": 30}, {
        "recommended_calories": 2000,
        "macro_targets": {"protein_g": 100.0},
        "policy_version": "nutrition-safety-v1",
    }, date(2026, 9, 10))

    assert result["version"] == 2
    assert connection.executed[0] == ("SELECT pg_advisory_xact_lock($1)", (42,))
    assert "revision.version>target.version" in connection.executed[1][0]
    assert "target.effective_to IS NULL OR target.effective_to >= $2" in connection.executed[1][0]
    assert connection.insert is not None
    insert_query, insert_arguments = connection.insert
    assert "SELECT min(effective_from)-1" in insert_query
    assert "SELECT max(version)+1" in insert_query
    assert "effective_from=$6" in insert_query
    assert insert_arguments[-1] == date(2026, 9, 10)


@pytest.mark.asyncio
async def test_current_target_orders_same_day_replacements_by_latest_revision() -> None:
    class CurrentPool:
        query = ""

        async def fetchrow(self, query: str, *_: object) -> None:
            self.query = query

    repository = NutritionRepository(_Settings())
    pool = CurrentPool()
    repository.pool = pool  # type: ignore[assignment]

    assert await repository.current_target(42, date(2026, 9, 10)) is None
    assert "ORDER BY effective_from DESC, version DESC" in pool.query


@pytest.mark.asyncio
async def test_daily_history_uses_latest_revision_for_same_day_target() -> None:
    class HistoryPool:
        query = ""

        async def fetch(self, query: str, *_: object) -> list[object]:
            self.query = query
            return []

    repository = NutritionRepository(_Settings())
    pool = HistoryPool()
    repository.pool = pool  # type: ignore[assignment]

    await repository.daily_history(
        42, date(2026, 9, 10), date(2026, 9, 10), "UTC"
    )

    assert "ORDER BY effective_from DESC, version DESC" in pool.query


@pytest.mark.asyncio
async def test_public_target_routes_scope_requests_to_authenticated_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": 42}
    calls: list[tuple[str, str, dict[str, object]]] = []

    async def request(method: str, path: str, **kwargs: object) -> dict[str, object]:
        calls.append((method, path, kwargs))
        return {"ok": True}

    monkeypatch.setattr(nutrition_agent_client, "request", request)
    transport = httpx.ASGITransport(app=app)
    payload = {"inputs": {"age": 30, "gender": "female", "weight_kg": 65,
                            "height_cm": 165, "activity_level": "moderate",
                            "fitness_goal": "maintenance"}}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/api/nutrition/targets/calculate", json=payload)).status_code == 200
        assert (await client.post("/api/nutrition/targets", json={**payload, "effective_from": "2026-09-10"})).status_code == 201
        assert (await client.get("/api/nutrition/targets/current", params={"date": "2026-09-10"})).status_code == 200

    assert [(method, path) for method, path, _ in calls] == [
        ("POST", "/v1/nutrition/users/42/targets/calculate"),
        ("POST", "/v1/nutrition/users/42/targets"),
        ("GET", "/v1/nutrition/users/42/targets/current"),
    ]
    assert calls[-1][2]["params"] == {"date": "2026-09-10"}