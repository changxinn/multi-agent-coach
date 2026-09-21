"""USDA FoodData Central provider with bounded retry behaviour."""

import asyncio
from decimal import Decimal
from typing import Protocol

import httpx

from .models import FoodDetails, FoodSearchResult


class FoodDataProvider(Protocol):
    async def search_foods(self, query: str) -> list[FoodSearchResult]: ...

    async def get_food_details(self, provider_food_id: str) -> FoodDetails: ...


class FoodDataProviderError(Exception):
    """An upstream food provider could not return a trustworthy result."""


class UsdaFoodDataCentralProvider:
    provider_name = "usda"
    base_url = "https://api.nal.usda.gov/fdc/v1"

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def search_foods(self, query: str) -> list[FoodSearchResult]:
        payload = await self._request("/foods/search", {"query": query, "pageSize": 20})
        return [
            FoodSearchResult(
                provider=self.provider_name,
                provider_food_id=str(food["fdcId"]),
                description=food.get("description", "Unknown food"),
                data_type=food.get("dataType"),
            )
            for food in payload.get("foods", [])
            if food.get("fdcId") is not None
        ]

    async def get_food_details(self, provider_food_id: str) -> FoodDetails:
        payload = await self._request(f"/food/{provider_food_id}", {})
        return self._food_details(payload, provider_food_id)

    async def list_foods(
        self, page_number: int, page_size: int, data_types: list[str]
    ) -> list[FoodDetails]:
        """Return one paged USDA abridged-food listing for offline catalogue import."""
        payload = await self._request(
            "/foods/list",
            {"pageNumber": page_number, "pageSize": page_size, "dataType": data_types},
        )
        return [
            self._food_details(food, str(food["fdcId"]))
            for food in payload
            if food.get("fdcId") is not None
        ]

    def _food_details(self, payload: dict, provider_food_id: str) -> FoodDetails:
        nutrients = self._nutrients(payload)
        serving_size = payload.get("servingSize")
        return FoodDetails(
            provider=self.provider_name,
            provider_food_id=str(payload.get("fdcId", provider_food_id)),
            description=payload.get("description", "Unknown food"),
            serving_size_g=self._decimal(serving_size),
            serving_description=payload.get("householdServingFullText"),
            calories_per_100g=nutrients.get("Energy"),
            protein_g_per_100g=nutrients.get("Protein"),
            carbohydrate_g_per_100g=nutrients.get("Carbohydrate, by difference"),
            fat_g_per_100g=nutrients.get("Total lipid (fat)"),
            fiber_g_per_100g=nutrients.get("Fiber, total dietary"),
            raw_response=payload,
        )

    async def _request(self, path: str, params: dict[str, object]) -> dict:
        if not self.api_key:
            raise FoodDataProviderError("USDA food lookup is not configured")
        request_params = {**params, "api_key": self.api_key}
        for attempt in range(3):
            try:
                response = await self.client.get(
                    f"{self.base_url}{path}", params=request_params
                )
                if (
                    response.status_code == 429 or response.status_code >= 500
                ) and attempt < 2:
                    await asyncio.sleep(0.25 * (2**attempt))
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                if attempt < 2:
                    await asyncio.sleep(0.25 * (2**attempt))
                    continue
                raise FoodDataProviderError(
                    "USDA food lookup is temporarily unavailable"
                ) from error
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 404:
                    raise FoodDataProviderError("USDA food was not found") from error
                raise FoodDataProviderError("USDA food lookup failed") from error
        raise FoodDataProviderError("USDA food lookup is temporarily unavailable")

    @staticmethod
    def _nutrients(payload: dict) -> dict[str, Decimal]:
        nutrients: dict[str, Decimal] = {}
        for nutrient in payload.get("foodNutrients", []):
            # Details responses nest the name; /foods/list supplies it at top level.
            name = (
                nutrient.get("nutrient", {}).get("name")
                or nutrient.get("nutrientName")
                or nutrient.get("name")
            )
            value = (
                nutrient.get("amount")
                if "amount" in nutrient
                else nutrient.get("value")
            )
            if name and value is not None:
                parsed = UsdaFoodDataCentralProvider._decimal(value)
                if parsed is not None:
                    nutrients[name] = parsed
        return nutrients

    @staticmethod
    def _decimal(value: object) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except ArithmeticError:
            return None
