"""Cache-first USDA food reference orchestration with safe fallback behavior."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from .config import Settings
from .tools.food_database import (
    FoodDatabaseClient,
    FoodDatabaseUnavailable,
    UsdaRequestLimiter,
)


class FoodReferenceService:
    """Keeps shared food responses useful when the optional USDA dependency fails."""

    _FAILURE_WINDOW = timedelta(seconds=30)
    _CIRCUIT_DURATION = timedelta(seconds=30)
    def __init__(
        self,
        repository: Any,
        api_key: str,
        now: Callable[[], datetime] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository
        self.api_key = api_key
        self._now = now or (lambda: datetime.now(UTC))
        self.settings = settings or Settings()
        self._limiter = UsdaRequestLimiter(
            self.settings.USDA_REQUESTS_PER_MINUTE,
            self.settings.USDA_REQUESTS_PER_HOUR,
            self.settings.USDA_REQUESTS_PER_DAY,
            now=self._now,
        )
        self._failures: deque[datetime] = deque()
        self._circuit_open_until: datetime | None = None

    def _circuit_is_open(self, now: datetime) -> bool:
        return self._circuit_open_until is not None and now < self._circuit_open_until

    def _record_failure(self, now: datetime) -> None:
        self._failures.append(now)
        while self._failures and now - self._failures[0] > self._FAILURE_WINDOW:
            self._failures.popleft()
        if len(self._failures) >= 5:
            self._circuit_open_until = now + self._CIRCUIT_DURATION

    def _age(self, item: dict, now: datetime) -> timedelta | None:
        fetched_at = item.get("fetched_at") or item.get("last_updated")
        return now - fetched_at if fetched_at else None

    def _stale(self, item: dict, now: datetime) -> bool:
        age = self._age(item, now)
        return age is not None and age > timedelta(days=self.settings.FOOD_CACHE_FRESH_DAYS)

    def _servable(self, item: dict, now: datetime) -> bool:
        age = self._age(item, now)
        return age is None or age <= timedelta(days=self.settings.FOOD_CACHE_MAX_STALE_DAYS)

    def _suppression_until(self, now: datetime) -> datetime:
        return now + timedelta(minutes=self.settings.USDA_REFRESH_SUPPRESSION_MINUTES)

    @staticmethod
    def _normalized_query(query: str) -> str:
        return " ".join(query.split()).casefold()

    def _client(self) -> FoodDatabaseClient:
        return FoodDatabaseClient(
            self.api_key,
            limiter=self._limiter,
            connect_timeout_seconds=self.settings.USDA_CONNECT_TIMEOUT_SECONDS,
            read_timeout_seconds=self.settings.USDA_READ_TIMEOUT_SECONDS,
            request_timeout_seconds=self.settings.USDA_REQUEST_TIMEOUT_SECONDS,
        )

    @staticmethod
    def _response_food(item: dict, *, cache_hit: bool, stale: bool = False) -> dict:
        return {
            "fdc_id": item["fdc_id"],
            "name": item["name"],
            "brand": item.get("brand"),
            "serving_size_g": item.get("serving_size_g"),
            "calories": item.get("calories"),
            "protein_g": item.get("protein_g"),
            "carbs_g": item.get("carbs_g"),
            "fat_g": item.get("fat_g"),
            "fiber_g": item.get("fiber_g"),
            "category": item.get("category"),
            "source": item.get("source", "cache"),
            "cache_hit": cache_hit,
            "last_updated": item.get("last_updated"),
            "_stale": stale,
        }

    async def search(self, query: str, limit: int, include_usda: bool) -> dict:
        now = self._now()
        cached = [
            item for item in await self.repository.search_food_cache(query, limit)
            if self._servable(item, now)
        ]
        stale = any(self._stale(item, now) for item in cached)
        items = [
            self._response_food(item, cache_hit=True, stale=self._stale(item, now))
            for item in cached
        ]
        needs_refresh = not cached or stale
        if not include_usda or not needs_refresh or not self.api_key:
            return self._result(
                items, "cache" if cached else "cache_only", "not_requested"
            )
        normalized_query = self._normalized_query(query)
        suppression = await self.repository.get_food_search_suppression(normalized_query)
        if suppression and suppression["suppression_until"] > now:
            return self._result(items, "cache" if cached else "cache_only", "unavailable")
        if cached and all(
            item.get("suppression_until") and item["suppression_until"] > now
            for item in cached
        ):
            return self._result(items, "cache", "unavailable")
        if self._circuit_is_open(now):
            return self._result(
                items, "cache" if cached else "cache_only", "circuit_open"
            )
        try:
            upstream = await self._client().search_and_get_details(
                query, min(limit, self.settings.USDA_MAX_RESULTS)
            )
            if not upstream:
                await self.repository.suppress_food_search(
                    normalized_query, self._suppression_until(now), "no_result"
                )
                return self._result(items, "cache" if cached else "cache_only", "fresh")
            stored = [
                await self.repository.upsert_cached_food(food) for food in upstream
            ]
        except FoodDatabaseUnavailable:
            self._record_failure(now)
            await self._suppress_cached(cached, now)
            await self.repository.suppress_food_search(
                normalized_query, self._suppression_until(now), "unavailable"
            )
            return self._result(
                items, "cache" if cached else "cache_only", "unavailable"
            )
        fresh = [self._response_food(item, cache_hit=False) for item in stored]
        by_id = {item["fdc_id"]: item for item in [*items, *fresh]}
        return self._result(
            list(by_id.values())[:limit],
            "cache_and_usda" if cached else "cache",
            "fresh",
        )

    async def detail(self, fdc_id: int) -> dict | None:
        now = self._now()
        cached = await self.repository.get_cached_food(fdc_id)
        if cached and not self._servable(cached, now):
            cached = None
        if self._circuit_is_open(now):
            return (
                self._response_food(
                    cached, cache_hit=True, stale=self._stale(cached, now)
                )
                if cached
                else None
            )
        if cached and (not self._stale(cached, now) or not self.api_key):
            return self._response_food(
                cached, cache_hit=True, stale=self._stale(cached, now)
            )
        if not self.api_key:
            return (
                self._response_food(cached, cache_hit=True, stale=True)
                if cached
                else None
            )
        if (
            cached
            and cached.get("suppression_until")
            and cached["suppression_until"] > now
        ):
            return self._response_food(cached, cache_hit=True, stale=True)
        try:
            food = await self._client().get_food_details(fdc_id)
            if food is None:
                return (
                    self._response_food(cached, cache_hit=True, stale=True)
                    if cached
                    else None
                )
            return self._response_food(
                await self.repository.upsert_cached_food(food), cache_hit=False
            )
        except FoodDatabaseUnavailable:
            self._record_failure(now)
            if cached:
                await self.repository.suppress_food_refresh(
                    fdc_id, self._suppression_until(now)
                )
                return self._response_food(cached, cache_hit=True, stale=True)
            return None

    async def _suppress_cached(self, cached: list[dict], now: datetime) -> None:
        for item in cached:
            await self.repository.suppress_food_refresh(
                item["fdc_id"], self._suppression_until(now)
            )

    @staticmethod
    def _result(items: list[dict], source: str, upstream_status: str) -> dict:
        stale = any(item.pop("_stale", False) for item in items)
        return {
            "items": items,
            "source": source,
            "upstream_status": upstream_status,
            "stale": stale,
        }
