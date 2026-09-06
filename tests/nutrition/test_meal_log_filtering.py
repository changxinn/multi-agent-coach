"""Meal-log date-filter contract coverage."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from app.api.routes.auth import get_current_user
from app.api.routes.nutrition import router
from app.services.nutrition_agent_client import nutrition_agent_client
from services.nutrition_agent.app import main as nutrition_main
from services.nutrition_agent.app.repository import NutritionRepository


class _Settings:
    @staticmethod
    def validated_schema() -> str:
        return "systemdb"


@pytest.mark.asyncio
async def test_public_meal_log_list_forwards_complete_date_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": 42}
    captured: dict[str, object] = {}

    async def list_meal_logs(user_id: int, params: dict[str, object]) -> dict[str, object]:
        captured.update(user_id=user_id, params=params)
        return {"items": [], "limit": 20, "offset": 0, "total": 0}

    monkeypatch.setattr(nutrition_agent_client, "list_meal_logs", list_meal_logs)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/nutrition/meal-logs",
                params={
                    "start_date": "2026-09-01",
                    "end_date": "2026-09-03",
                    "timezone": "America/New_York",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured == {
        "user_id": 42,
        "params": {
            "limit": 20,
            "offset": 0,
            "start_date": "2026-09-01",
            "end_date": "2026-09-03",
            "timezone": "America/New_York",
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start_date", "end_date", "timezone"),
    [
        (date(2026, 9, 1), None, "UTC"),
        (date(2026, 9, 3), date(2026, 9, 1), "UTC"),
        (date(2026, 9, 1), date(2026, 10, 2), "UTC"),
        (date(2026, 9, 1), date(2026, 9, 3), "Not/A_Timezone"),
    ],
)
async def test_private_meal_log_list_rejects_incomplete_or_invalid_date_filter(
    start_date: date | None, end_date: date | None, timezone: str | None
) -> None:
    with pytest.raises(HTTPException) as error:
        await nutrition_main.list_meals(42, 20, 0, start_date, end_date, timezone)

    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_repository_meal_log_date_filter_uses_timezone_bounded_parameterized_query() -> None:
    class Pool:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, tuple[object, ...]]] = []

        async def fetch(self, query: str, *args: object) -> list[object]:
            self.calls.append(("fetch", query, args))
            return []

        async def fetchval(self, query: str, *args: object) -> int:
            self.calls.append(("fetchval", query, args))
            return 0

    repository = NutritionRepository(_Settings())
    pool = Pool()
    repository.pool = pool  # type: ignore[assignment]

    items, total = await repository.list_meals(
        42,
        20,
        5,
        date(2026, 9, 1),
        date(2026, 9, 3),
        "America/New_York",
    )

    assert items == []
    assert total == 0
    _, query, args = pool.calls[0]
    assert "logged_at >= ($2::date::timestamp AT TIME ZONE $4)" in query
    assert "logged_at < (($3::date + 1)::timestamp AT TIME ZONE $4)" in query
    assert "ORDER BY logged_at DESC,id DESC LIMIT $5 OFFSET $6" in query
    assert args == (
        42,
        date(2026, 9, 1),
        date(2026, 9, 3),
        "America/New_York",
        20,
        5,
    )