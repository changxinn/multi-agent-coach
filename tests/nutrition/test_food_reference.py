"""Cache-first USDA fallback and resilience behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from services.nutrition_agent.app.food_reference import FoodReferenceService
from services.nutrition_agent.app.tools.food_database import (
    FoodDatabaseClient,
    FoodDatabaseRateLimited,
    FoodDatabaseUnavailable,
    UsdaRequestLimiter,
)

NOW = datetime(2026, 8, 31, tzinfo=UTC)


class FakeRepository:
    def __init__(self, items: list[dict] | None = None) -> None:
        self.items = items or []
        self.upserted: list[dict] = []
        self.suppressed: list[int] = []
        self.search_suppressions: dict[str, dict] = {}

    async def search_food_cache(self, _: str, __: int) -> list[dict]:
        return self.items

    async def get_cached_food(self, fdc_id: int) -> dict | None:
        return next((item for item in self.items if item["fdc_id"] == fdc_id), None)

    async def upsert_cached_food(self, food: dict) -> dict:
        self.upserted.append(food)
        return {
            **food,
            "source": "usda",
            "last_updated": NOW,
            "fetched_at": NOW,
            "refresh_after": NOW + timedelta(days=30),
        }

    async def suppress_food_refresh(self, fdc_id: int, _: datetime) -> None:
        self.suppressed.append(fdc_id)

    async def get_food_search_suppression(self, query: str) -> dict | None:
        return self.search_suppressions.get(query)

    async def suppress_food_search(self, query: str, until: datetime, reason: str) -> None:
        self.search_suppressions[query] = {
            "normalized_query": query,
            "suppression_until": until,
            "reason": reason,
        }


def stale_food() -> dict:
    return {
        "fdc_id": 1,
        "name": "Oats",
        "source": "usda",
        "last_updated": NOW - timedelta(days=31),
        "fetched_at": NOW - timedelta(days=31),
        "refresh_after": NOW - timedelta(seconds=1),
        "suppression_until": None,
    }


@pytest.mark.asyncio
async def test_no_key_returns_cache_only_without_upstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    service = FoodReferenceService(repository, "", now=lambda: NOW)

    result = await service.search("oats", 20, include_usda=True)

    assert result == {
        "items": [],
        "source": "cache_only",
        "upstream_status": "not_requested",
        "stale": False,
    }


@pytest.mark.asyncio
async def test_cache_miss_enriches_and_upserts_usda_food(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    service = FoodReferenceService(repository, "key", now=lambda: NOW)

    async def upstream(self: FoodDatabaseClient, query: str, limit: int) -> list[dict]:
        assert (query, limit) == ("oats", 20)
        return [{"fdc_id": 9, "name": "Rolled oats", "calories": 379.0}]

    monkeypatch.setattr(FoodDatabaseClient, "search_and_get_details", upstream)
    result = await service.search("oats", 20, include_usda=True)

    assert repository.upserted == [
        {"fdc_id": 9, "name": "Rolled oats", "calories": 379.0}
    ]
    assert result["source"] == "cache"
    assert result["upstream_status"] == "fresh"
    assert result["items"][0]["cache_hit"] is False


@pytest.mark.asyncio
async def test_upstream_outage_returns_stale_cache_without_error_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository([stale_food()])
    service = FoodReferenceService(repository, "key", now=lambda: NOW)

    async def unavailable(*_: object, **__: object) -> list[dict]:
        raise FoodDatabaseUnavailable("upstream secret error")

    monkeypatch.setattr(FoodDatabaseClient, "search_and_get_details", unavailable)
    result = await service.search("oats", 20, include_usda=True)

    assert result["source"] == "cache"
    assert result["upstream_status"] == "unavailable"
    assert result["stale"] is True
    assert repository.suppressed == [1]
    assert "secret" not in str(result)


@pytest.mark.asyncio
async def test_no_result_is_query_suppressed_for_fifteen_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeRepository()
    service = FoodReferenceService(repository, "key", now=lambda: NOW)
    calls = 0

    async def no_results(*_: object, **__: object) -> list[dict]:
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(FoodDatabaseClient, "search_and_get_details", no_results)
    assert (await service.search("  OATS  ", 20, include_usda=True))["upstream_status"] == "fresh"
    assert (await service.search("oats", 20, include_usda=True))["upstream_status"] == "unavailable"
    assert calls == 1
    assert repository.search_suppressions["oats"]["reason"] == "no_result"
    assert repository.search_suppressions["oats"]["suppression_until"] == NOW + timedelta(minutes=15)


@pytest.mark.asyncio
async def test_expired_cache_is_not_served_when_usda_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expired = stale_food() | {"fetched_at": NOW - timedelta(days=181)}
    service = FoodReferenceService(FakeRepository([expired]), "key", now=lambda: NOW)

    async def unavailable(*_: object, **__: object) -> list[dict]:
        raise FoodDatabaseUnavailable()

    monkeypatch.setattr(FoodDatabaseClient, "search_and_get_details", unavailable)
    result = await service.search("oats", 20, include_usda=True)
    assert result["items"] == []
    assert result["stale"] is False


@pytest.mark.asyncio
async def test_five_failures_open_circuit_and_skip_next_upstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FoodReferenceService(FakeRepository(), "key", now=lambda: NOW)
    calls = 0

    async def unavailable(*_: object, **__: object) -> list[dict]:
        nonlocal calls
        calls += 1
        raise FoodDatabaseUnavailable()

    monkeypatch.setattr(FoodDatabaseClient, "search_and_get_details", unavailable)
    for index in range(5):
        result = await service.search(f"oats {index}", 20, include_usda=True)
        assert result["upstream_status"] == "unavailable"
    result = await service.search("oats", 20, include_usda=True)

    assert calls == 5
    assert result["upstream_status"] == "circuit_open"


def test_per_instance_limiter_enforces_minute_cap() -> None:
    limiter = UsdaRequestLimiter(2, 1000, 10000, now=lambda: NOW)
    limiter.acquire()
    limiter.acquire()
    with pytest.raises(FoodDatabaseRateLimited):
        limiter.acquire()
