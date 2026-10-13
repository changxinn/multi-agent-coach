"""Authenticated gateway client for the Training Agent private service."""

import logging
from datetime import date
from time import perf_counter
from typing import Any

import httpx
from fastapi.encoders import jsonable_encoder

from app.config import get_settings

logger = logging.getLogger(__name__)
GENERATION_OPERATIONS = frozenset(
    {
        "programs/generate",
        "programs/adapt",
        "daily-workout",
        "exercises/search",
    }
)


class TrainingAgentUnavailableError(RuntimeError):
    """Raised when the private Training Agent cannot serve a gateway request."""


class TrainingAgentClient:
    async def _post(
        self, path: str, payload: dict[str, Any], *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        settings = get_settings()
        if not settings.INTERNAL_SERVICE_TOKEN:
            raise TrainingAgentUnavailableError("Training service is not configured")
        timeout_seconds = (
            settings.TRAINING_AGENT_GENERATION_TIMEOUT_SECONDS
            if path in GENERATION_OPERATIONS
            else settings.TRAINING_AGENT_TIMEOUT_SECONDS
        )
        started_at = perf_counter()
        logger.info(
            "Training Agent request started operation=%s timeout_seconds=%.1f",
            path,
            timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout_seconds, connect=2.0)
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
            logger.info(
                "Training Agent request completed operation=%s status_code=%d elapsed_seconds=%.3f",
                path,
                response.status_code,
                perf_counter() - started_at,
            )
            return response.json()
        except httpx.HTTPError as error:
            logger.warning(
                "Training Agent request failed operation=%s error_type=%s elapsed_seconds=%.3f",
                path,
                type(error).__name__,
                perf_counter() - started_at,
            )
            raise TrainingAgentUnavailableError(
                "Training service request timed out; check saved programs before trying again"
                if isinstance(error, httpx.TimeoutException)
                and path.startswith("programs/")
                else "Training service is temporarily unavailable"
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
        return await self._post(
            "exercises/search", {"user_id": user_id, "query": query}
        )

    async def exercise_lookup(self, user_id: int, query: str) -> dict[str, Any]:
        return await self._post(
            "exercises/lookup", {"user_id": user_id, "query": query}
        )

    async def generate_program(
        self, user_id: int, recovery_status: str
    ) -> dict[str, Any]:
        return await self._post(
            "programs/generate",
            {"user_id": user_id, "recovery_status": recovery_status},
        )

    async def list_programs(self, user_id: int) -> dict[str, Any]:
        return await self._post("programs/list", {"user_id": user_id})

    async def adapt_program(
        self, user_id: int, reason: str, recovery_status: str
    ) -> dict[str, Any]:
        return await self._post(
            "programs/adapt",
            {"user_id": user_id, "reason": reason, "recovery_status": recovery_status},
        )

    async def profile(self, user_id: int) -> dict[str, Any]:
        return await self._post("profile/get", {"user_id": user_id})

    async def update_profile(
        self, user_id: int, values: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._post("profile/update", {"user_id": user_id, **values})

    async def preferences(self, user_id: int) -> dict[str, Any]:
        return await self._post("preferences/get", {"user_id": user_id})

    async def update_preferences(
        self, user_id: int, values: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._post("preferences/update", {"user_id": user_id, **values})

    async def log_workout(
        self, user_id: int, values: dict[str, Any], idempotency_key: str | None
    ) -> dict[str, Any]:
        return await self._post(
            "workouts/log",
            {"user_id": user_id, **values},
            idempotency_key=idempotency_key,
        )

    async def list_workouts(
        self, user_id: int, days: int, limit: int
    ) -> dict[str, Any]:
        result = await self._post("workouts/list", {"user_id": user_id, "days": days})
        return {"items": result.get("items", [])[:limit]}

    async def progress(self, user_id: int, days: int) -> dict[str, Any]:
        return await self._post("progress", {"user_id": user_id, "days": days})

    async def context(self, user_id: int) -> dict[str, Any]:
        return await self._post("context", {"user_id": user_id})


training_agent_client = TrainingAgentClient()
