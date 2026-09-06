"""Bounded USDA FoodData Central client returning normalized food records only."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx


class FoodDatabaseUnavailable(Exception):
    """USDA is unreachable or returned an invalid/unusable response."""


class FoodDatabaseRateLimited(FoodDatabaseUnavailable):
    """The local per-instance USDA request allowance has been exhausted."""


class UsdaRequestLimiter:
    """In-memory rolling-window cap covering every USDA HTTP request."""

    def __init__(self, per_minute: int, per_hour: int, per_day: int, now: Callable[[], datetime] | None = None) -> None:
        self._limits = ((timedelta(minutes=1), per_minute), (timedelta(hours=1), per_hour), (timedelta(days=1), per_day))
        self._requests: deque[datetime] = deque()
        self._now = now or (lambda: datetime.now(UTC))

    def acquire(self) -> None:
        now = self._now()
        self._requests.append(now)
        for window, limit in self._limits:
            if sum(requested_at > now - window for requested_at in self._requests) > limit:
                self._requests.pop()
                raise FoodDatabaseRateLimited()
        while self._requests and self._requests[0] <= now - timedelta(days=1):
            self._requests.popleft()


class FoodDatabaseClient:
    """Small USDA client; callers own cache and circuit-breaker policy."""

    def __init__(self, api_key: str, base_url: str = "https://api.nal.usda.gov/fdc/v1", *, limiter: UsdaRequestLimiter | None = None, connect_timeout_seconds: float = 2.0, read_timeout_seconds: float = 5.0, request_timeout_seconds: float = 10.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.limiter = limiter
        self.timeout = httpx.Timeout(request_timeout_seconds, connect=connect_timeout_seconds, read=read_timeout_seconds, write=read_timeout_seconds, pool=connect_timeout_seconds)

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(2):
            try:
                if self.limiter:
                    self.limiter.acquire()
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        f"{self.base_url}{path}",
                        params={"api_key": self.api_key, **params},
                    )
                if response.status_code in {502, 503, 504} and attempt == 0:
                    await asyncio.sleep(0.125)
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise FoodDatabaseUnavailable()
                return payload
            except FoodDatabaseRateLimited:
                raise
            except (httpx.ConnectTimeout, httpx.ReadTimeout):
                if attempt == 0:
                    await asyncio.sleep(0.125)
                    continue
                raise FoodDatabaseUnavailable() from None
            except (httpx.HTTPError, ValueError):
                raise FoodDatabaseUnavailable() from None
        raise FoodDatabaseUnavailable()

    async def search_food(
        self, query: str, page_size: int = 10
    ) -> list[dict[str, Any]]:
        payload = await self._get(
            "/foods/search", {"query": query, "pageSize": min(page_size, 50)}
        )
        foods = payload.get("foods")
        if not isinstance(foods, list):
            raise FoodDatabaseUnavailable()
        return [
            food
            for food in foods
            if isinstance(food, dict) and isinstance(food.get("fdcId"), int)
        ]

    @staticmethod
    def _nutrients(food: dict[str, Any]) -> dict[int, float]:
        values: dict[int, float] = {}
        for entry in food.get("foodNutrients", []):
            if not isinstance(entry, dict):
                continue
            nutrient = (
                entry.get("nutrient")
                if isinstance(entry.get("nutrient"), dict)
                else entry
            )
            nutrient_id = nutrient.get("id") or nutrient.get("nutrientId")
            amount = entry.get("amount") or entry.get("value")
            if isinstance(nutrient_id, int) and isinstance(amount, (int, float)):
                values[nutrient_id] = float(amount)
        return values

    @classmethod
    def normalize(cls, food: dict[str, Any]) -> dict[str, Any] | None:
        fdc_id, name = food.get("fdcId"), food.get("description")
        if not isinstance(fdc_id, int) or not isinstance(name, str) or not name.strip():
            return None
        nutrients = cls._nutrients(food)
        serving = food.get("servingSize")
        return {
            "fdc_id": fdc_id,
            "name": name.strip(),
            "brand": food.get("brandOwner") or None,
            "serving_size_g": int(serving)
            if isinstance(serving, (int, float)) and serving > 0
            else None,
            "calories": nutrients.get(1008),
            "protein_g": nutrients.get(1003),
            "carbs_g": nutrients.get(1005),
            "fat_g": nutrients.get(1004),
            "fiber_g": nutrients.get(1079),
            "category": food.get("foodCategory") or None,
        }

    async def get_food_details(self, fdc_id: int) -> dict[str, Any] | None:
        return self.normalize(await self._get(f"/food/{fdc_id}", {"format": "full"}))

    async def search_and_get_details(
        self, query: str, max_results: int = 5
    ) -> list[dict[str, Any]]:
        results = await self.search_food(query, max_results)
        foods: list[dict[str, Any]] = []
        for result in results[:max_results]:
            detail = await self.get_food_details(result["fdcId"])
            if detail:
                foods.append(detail)
        return foods
