"""Typed asynchronous client for the authoritative private Nutrition Agent."""
from datetime import date
from uuid import uuid4
from typing import Any

import httpx

from app.config import get_settings
from app.services.nutrition_service import (
    NutritionFoodDataError,
    NutritionNotFoundError,
    NutritionProfileIncompleteError,
)


class NutritionAgentUnavailableError(Exception):
    """The authoritative Nutrition Agent could not be reached."""


class NutritionAgentClient:
    """Forwards authenticated gateway operations; mutation calls are never retried."""

    async def _post(self, path: str, payload: dict[str, Any], *, idempotency_key: str | None = None) -> Any:
        settings = get_settings()
        if not settings.INTERNAL_SERVICE_TOKEN:
            raise NutritionAgentUnavailableError("Nutrition service is not configured")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=2.0)) as client:
                response = await client.post(
                    f"{settings.NUTRITION_AGENT_URL.rstrip('/')}/v1/nutrition/{path}",
                    headers={
                        "X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN,
                        "X-Request-ID": str(uuid4()),
                        **({"Idempotency-Key": idempotency_key} if idempotency_key else {}),
                    },
                    json=payload,
                )
        except httpx.HTTPError as error:
            raise NutritionAgentUnavailableError("Nutrition service is temporarily unavailable") from error
        if response.status_code == 404:
            raise NutritionNotFoundError(response.json().get("detail", "Nutrition resource not found"))
        if response.status_code == 422:
            raise NutritionProfileIncompleteError(response.json().get("detail", "Invalid nutrition request"))
        if response.status_code == 503:
            raise NutritionFoodDataError(response.json().get("detail", "Nutrition service unavailable"))
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise NutritionAgentUnavailableError("Nutrition service returned an unexpected error") from error
        return response.json()

    async def get_profile(self, user_id: int) -> dict[str, Any]:
        return await self._post("profile/get", {"user_id": user_id})

    async def update_profile(self, user_id: int, values: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        return await self._post("profile/save", {"user_id": user_id, "values": values}, idempotency_key=idempotency_key)

    async def calculate_targets(self, user_id: int, confirm_apply: bool, idempotency_key: str | None = None) -> dict[str, Any]:
        return await self._post("targets/calculate-for-user", {"user_id": user_id, "confirm_apply": confirm_apply}, idempotency_key=idempotency_key)

    async def get_active_target(self, user_id: int) -> dict[str, Any]:
        return await self._post("targets/active", {"user_id": user_id})

    async def search_foods(self, user_id: int, query: str) -> list[dict[str, Any]]:
        return (await self._post("foods/search", {"user_id": user_id, "query": query}))["items"]

    async def get_food_catalogue(self, user_id: int, limit: int = 200) -> list[dict[str, Any]]:
        return (await self._post("foods/catalogue", {"user_id": user_id, "limit": limit}))["items"]

    async def get_food(self, user_id: int, food_id: str) -> dict[str, Any]:
        return await self._post("foods/detail", {"user_id": user_id, "food_id": food_id})

    async def create_meal(self, user_id: int, payload: Any, idempotency_key: str | None = None) -> dict[str, Any]:
        return await self._post("meals/create", {"user_id": user_id, **payload.model_dump(mode="json")}, idempotency_key=idempotency_key)

    async def list_meals(self, user_id: int, for_date: date) -> list[dict[str, Any]]:
        return (await self._post("meals/list", {"user_id": user_id, "date": for_date.isoformat()}))["items"]

    async def replace_meal(self, user_id: int, meal_id: int, payload: Any, idempotency_key: str | None = None) -> dict[str, Any]:
        values = payload.model_dump(mode="json", exclude={"meal_id"})
        return await self._post("meals/replace", {"user_id": user_id, "meal_id": meal_id, **values}, idempotency_key=idempotency_key)

    async def delete_meal(self, user_id: int, meal_id: int, idempotency_key: str | None = None) -> None:
        await self._post("meals/delete", {"user_id": user_id, "meal_id": meal_id}, idempotency_key=idempotency_key)

    async def get_daily_summary(self, user_id: int, for_date: date) -> dict[str, Any]:
        return await self._post("daily-summary", {"user_id": user_id, "date": for_date.isoformat()})

    async def get_adherence(self, user_id: int, from_date: date, to_date: date) -> list[dict[str, Any]]:
        return (await self._post("adherence", {"user_id": user_id, "from_date": from_date.isoformat(), "to_date": to_date.isoformat()}))["items"]

    async def chat(self, user_id: int, message: str) -> dict[str, Any]:
        return await self._post("chat", {"user_id": user_id, "message": message})

    def chat_sync(self, user_id: int, message: str) -> dict[str, Any]:
        """Synchronous entry point for the existing LangGraph worker thread."""
        settings = get_settings()
        if not settings.INTERNAL_SERVICE_TOKEN:
            raise NutritionAgentUnavailableError("Nutrition service is not configured")
        try:
            response = httpx.post(
                f"{settings.NUTRITION_AGENT_URL.rstrip('/')}/v1/nutrition/chat",
                headers={
                    "X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN,
                    "X-Request-ID": str(uuid4()),
                },
                json={"user_id": user_id, "message": message},
                timeout=httpx.Timeout(10.0, connect=2.0),
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as error:
            raise NutritionAgentUnavailableError("Nutrition service is temporarily unavailable") from error


nutrition_agent_client = NutritionAgentClient()