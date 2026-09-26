"""Typed asynchronous client for the authoritative private Nutrition Agent."""

import logging
from datetime import date
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
from fastapi.encoders import jsonable_encoder

from app.config import get_settings
from app.services.nutrition_service import (
    NutritionFoodDataError,
    NutritionNotFoundError,
    NutritionProfileIncompleteError,
)

logger = logging.getLogger(__name__)


class NutritionAgentUnavailableError(Exception):
    """The authoritative Nutrition Agent could not be reached."""


class NutritionMealPlanValidationError(Exception):
    """The Nutrition Agent rejected a meal-plan safety or lifecycle operation."""


class NutritionAgentClient:
    """Forwards authenticated gateway operations; mutation calls are never retried."""

    async def _post(
        self, path: str, payload: dict[str, Any], *, idempotency_key: str | None = None
    ) -> Any:
        settings = get_settings()
        if not settings.INTERNAL_SERVICE_TOKEN:
            raise NutritionAgentUnavailableError("Nutrition service is not configured")
        request_id = str(uuid4())
        timeout_seconds = (
            settings.NUTRITION_MEAL_PLAN_GENERATION_TIMEOUT_SECONDS
            if path == "meal-plans/generate"
            else 10.0
        )
        started_at = perf_counter()
        logger.info(
            "Nutrition Agent request started operation=%s request_id=%s timeout_seconds=%.1f",
            path,
            request_id,
            timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout_seconds, connect=2.0)
            ) as client:
                response = await client.post(
                    f"{settings.NUTRITION_AGENT_URL.rstrip('/')}/v1/nutrition/{path}",
                    headers={
                        "X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN,
                        "X-Request-ID": request_id,
                        **(
                            {"Idempotency-Key": idempotency_key}
                            if idempotency_key
                            else {}
                        ),
                    },
                    json=jsonable_encoder(payload),
                )
        except httpx.HTTPError as error:
            logger.warning(
                "Nutrition Agent request failed operation=%s request_id=%s error_type=%s elapsed_seconds=%.3f",
                path,
                request_id,
                type(error).__name__,
                perf_counter() - started_at,
            )
            raise NutritionAgentUnavailableError(
                "Nutrition service is temporarily unavailable"
            ) from error
        logger.info(
            "Nutrition Agent request completed operation=%s request_id=%s status_code=%d elapsed_seconds=%.3f",
            path,
            request_id,
            response.status_code,
            perf_counter() - started_at,
        )
        if response.status_code == 404 and path in {
            "meal-plans/get",
            "meal-plans/confirm",
            "meal-plans/archive",
            "meal-plans/delete",
            "targets/active",
        }:
            raise NutritionNotFoundError(
                response.json().get("detail", "Nutrition resource not found")
            )
        if response.status_code == 404:
            raise NutritionAgentUnavailableError(
                f"Nutrition service does not support operation: {path}"
            )
        if response.status_code == 422:
            detail = response.json().get("detail", "Invalid nutrition request")
            if path in {
                "meal-plans/confirm",
                "meal-plans/archive",
                "meal-plans/delete",
                "meal-plans/generate",
            }:
                raise NutritionMealPlanValidationError(detail)
            raise NutritionProfileIncompleteError(detail)
        if response.status_code == 503:
            raise NutritionFoodDataError(
                response.json().get("detail", "Nutrition service unavailable")
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise NutritionAgentUnavailableError(
                "Nutrition service returned an unexpected error"
            ) from error
        return response.json()

    def respond(
        self,
        *,
        user_id: int,
        messages: list[dict[str, Any]],
        user_profile: dict[str, Any],
        nutrition_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Call the conversational Nutrition Agent from the synchronous graph node."""
        settings = get_settings()
        if not settings.INTERNAL_SERVICE_TOKEN:
            raise NutritionAgentUnavailableError("Nutrition service is not configured")
        try:
            response = httpx.post(
                f"{settings.NUTRITION_AGENT_URL.rstrip('/')}/v1/nutrition/chat",
                headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
                json=jsonable_encoder(
                    {
                        "user_id": user_id,
                        "messages": messages,
                        "user_profile": user_profile,
                        "nutrition_context": nutrition_context,
                    }
                ),
                timeout=httpx.Timeout(30.0, connect=2.0),
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise NutritionAgentUnavailableError(
                "Nutrition service is temporarily unavailable"
            ) from error
        payload = response.json()
        if (
            not isinstance(payload.get("message"), str)
            or not payload["message"].strip()
        ):
            raise NutritionAgentUnavailableError(
                "Nutrition service returned an invalid response"
            )
        return payload

    async def calculate_targets(
        self,
        user_id: int,
        confirm_apply: bool,
        profile: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return await self._post(
            "targets/calculate-for-user",
            {"user_id": user_id, "confirm_apply": confirm_apply, "profile": profile},
            idempotency_key=idempotency_key,
        )

    async def get_active_target(self, user_id: int) -> dict[str, Any]:
        return await self._post("targets/active", {"user_id": user_id})

    async def search_foods(self, user_id: int, query: str) -> list[dict[str, Any]]:
        return (await self._post("foods/search", {"user_id": user_id, "query": query}))[
            "items"
        ]

    async def get_food_catalogue(self, user_id: int) -> list[dict[str, Any]]:
        return (await self._post("foods/catalogue", {"user_id": user_id}))["items"]

    async def create_meal_plan(
        self,
        user_id: int,
        payload: Any,
        idempotency_key: str | None = None,
        *,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._post(
            "meal-plans/create",
            {
                "user_id": user_id,
                "profile": profile or {},
                **payload.model_dump(mode="json"),
            },
            idempotency_key=idempotency_key,
        )

    async def generate_meal_plan(
        self,
        user_id: int,
        payload: Any,
        idempotency_key: str | None = None,
        *,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._post(
            "meal-plans/generate",
            {
                "user_id": user_id,
                "profile": profile or {},
                **payload.model_dump(mode="json"),
            },
            idempotency_key=idempotency_key,
        )

    async def get_active_meal_plan(
        self, user_id: int, for_date: date
    ) -> dict[str, Any] | None:
        return (
            await self._post(
                "meal-plans/active", {"user_id": user_id, "date": for_date.isoformat()}
            )
        )["meal_plan"]

    async def get_meal_plan(self, user_id: int, meal_plan_id: int) -> dict[str, Any]:
        return await self._post(
            "meal-plans/get", {"user_id": user_id, "meal_plan_id": meal_plan_id}
        )

    async def list_meal_plans(self, user_id: int) -> list[dict[str, Any]]:
        return (await self._post("meal-plans/list", {"user_id": user_id}))["items"]

    async def confirm_meal_plan(
        self,
        user_id: int,
        meal_plan_id: int,
        idempotency_key: str | None = None,
        *,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._post(
            "meal-plans/confirm",
            {
                "user_id": user_id,
                "meal_plan_id": meal_plan_id,
                "profile": profile or {},
            },
            idempotency_key=idempotency_key,
        )

    async def archive_meal_plan(
        self, user_id: int, meal_plan_id: int, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        return await self._post(
            "meal-plans/archive",
            {"user_id": user_id, "meal_plan_id": meal_plan_id},
            idempotency_key=idempotency_key,
        )

    async def delete_meal_plan(
        self, user_id: int, meal_plan_id: int, idempotency_key: str | None = None
    ) -> dict[str, bool]:
        return await self._post(
            "meal-plans/delete",
            {"user_id": user_id, "meal_plan_id": meal_plan_id},
            idempotency_key=idempotency_key,
        )

    async def get_nutrition_context(
        self, user_id: int, for_date: date
    ) -> dict[str, Any]:
        return await self._post(
            "context", {"user_id": user_id, "date": for_date.isoformat()}
        )


nutrition_agent_client = NutritionAgentClient()
