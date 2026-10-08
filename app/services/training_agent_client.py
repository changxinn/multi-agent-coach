"""Authenticated gateway client for the Training Agent private service."""

from datetime import date
from typing import Any

import httpx
from fastapi.encoders import jsonable_encoder

from app.config import get_settings


class TrainingAgentUnavailableError(RuntimeError):
    """Raised when the private Training Agent cannot serve a gateway request."""


class TrainingAgentClient:
    async def _post(
        self, path: str, payload: dict[str, Any], *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        settings = get_settings()
        if not settings.INTERNAL_SERVICE_TOKEN:
            raise TrainingAgentUnavailableError("Training service is not configured")
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    settings.TRAINING_AGENT_TIMEOUT_SECONDS, connect=2.0
                )
            ) as client:
                response = await client.post(
                    f"{settings.TRAINING_AGENT_URL.rstrip('/')}/v1/training/{path}",
                    headers={
                        "X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN,
                        **(
                            {"Idempotency-Key": idempotency_key}
                            if idempotency_key
                            else {}
                        ),
                    },
                    json=jsonable_encoder(payload),
                )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as error:
            raise TrainingAgentUnavailableError(
                "Training service is temporarily unavailable"
            ) from error

    def respond(
        self, user_id: int, messages: list[dict[str, Any]], user_profile: dict[str, Any]
    ) -> dict[str, Any]:
        """Synchronous bridge used by the LangGraph worker thread."""
        settings = get_settings()
        if not settings.INTERNAL_SERVICE_TOKEN:
            raise TrainingAgentUnavailableError("Training service is not configured")
        try:
            response = httpx.post(
                f"{settings.TRAINING_AGENT_URL.rstrip('/')}/v1/training/chat",
                headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
                json=jsonable_encoder(
                    {
                        "user_id": user_id,
                        "messages": messages,
                        "user_profile": user_profile,
                    }
                ),
                timeout=settings.TRAINING_AGENT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as error:
            raise TrainingAgentUnavailableError(
                "Training service is temporarily unavailable"
            ) from error

    async def daily_workout(
        self,
        *,
        user_id: int,
        workout_date: date,
        refresh: bool,
        recovery_status: str,
    ) -> dict[str, Any]:
        return await self._post(
            "daily-workout",
            {
                "user_id": user_id,
                "date": workout_date.isoformat(),
                "refresh": refresh,
                "recovery_status": recovery_status,
            },
        )

    async def exercises_search(self, user_id: int, query: str) -> dict[str, Any]:
        return await self._post("exercises/search", {"user_id": user_id, "query": query})

    async def exercise_lookup(self, user_id: int, query: str) -> dict[str, Any]:
        return await self._post("exercises/lookup", {"user_id": user_id, "query": query})

    async def generate_program(self, user_id: int, recovery_status: str) -> dict[str, Any]:
        return await self._post("programs/generate", {"user_id": user_id, "recovery_status": recovery_status})

    async def list_programs(self, user_id: int) -> dict[str, Any]:
        return await self._post("programs/list", {"user_id": user_id})

    async def adapt_program(self, user_id: int, reason: str, recovery_status: str) -> dict[str, Any]:
        return await self._post("programs/adapt", {"user_id": user_id, "reason": reason, "recovery_status": recovery_status})

    async def profile(self, user_id: int) -> dict[str, Any]:
        return await self._post("profile/get", {"user_id": user_id})

    async def update_profile(self, user_id: int, values: dict[str, Any]) -> dict[str, Any]:
        return await self._post("profile/update", {"user_id": user_id, **values})

    async def preferences(self, user_id: int) -> dict[str, Any]:
        return await self._post("preferences/get", {"user_id": user_id})

    async def update_preferences(self, user_id: int, values: dict[str, Any]) -> dict[str, Any]:
        return await self._post("preferences/update", {"user_id": user_id, **values})

    async def log_workout(self, user_id: int, values: dict[str, Any], idempotency_key: str | None) -> dict[str, Any]:
        return await self._post(
            "workouts/log", {"user_id": user_id, **values}, idempotency_key=idempotency_key
        )

    async def list_workouts(self, user_id: int, days: int, limit: int) -> dict[str, Any]:
        result = await self._post("workouts/list", {"user_id": user_id, "days": days})
        return {"items": result.get("items", [])[:limit]}

    async def progress(self, user_id: int, days: int) -> dict[str, Any]:
        return await self._post("progress", {"user_id": user_id, "days": days})

    async def context(self, user_id: int) -> dict[str, Any]:
        return await self._post("context", {"user_id": user_id})


training_agent_client = TrainingAgentClient()
