"""Async, token-authenticated client for the private Nutrition Agent service."""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.api.request_context import request_id
from app.config import get_settings


class NutritionAgentError(Exception):
    """Sanitized Nutrition Agent dependency failure."""

    def __init__(
        self,
        status_code: int = 503,
        code: str | None = None,
        message: str | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message


def validation_error_message(detail: Any) -> str | None:
    """Return one bounded, input-free message from FastAPI validation details."""
    if not isinstance(detail, list):
        return None
    for item in detail:
        if not isinstance(item, dict):
            continue
        message = item.get("msg")
        if isinstance(message, str) and (normalized := message.strip()):
            return normalized[:200]
    return None


class NutritionAgentClient:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._failure_times: deque[float] = deque()
        self._circuit_open_until = 0.0
        self._half_open_probe_in_flight = False

    @staticmethod
    def _is_retryable_method(method: str) -> bool:
        return method.upper() in {"GET", "HEAD", "OPTIONS"}

    @staticmethod
    def _is_qualifying_response(response: httpx.Response) -> bool:
        return response.status_code in {502, 503, 504}

    @staticmethod
    def _is_qualifying_exception(error: httpx.HTTPError) -> bool:
        return isinstance(error, (httpx.ConnectTimeout, httpx.ReadTimeout))

    def _before_request(self) -> bool:
        """Reject open-circuit calls and reserve an expired-circuit probe."""
        now = time.monotonic()
        while self._failure_times and self._failure_times[0] <= now - 30.0:
            self._failure_times.popleft()
        if not self._circuit_open_until:
            return False
        if now < self._circuit_open_until or self._half_open_probe_in_flight:
            raise NutritionAgentError()
        self._half_open_probe_in_flight = True
        return True

    def _record_success(self) -> None:
        self._failure_times.clear()
        self._circuit_open_until = 0.0
        self._half_open_probe_in_flight = False

    def _record_qualifying_failure(self, is_half_open_probe: bool) -> None:
        now = time.monotonic()
        self._failure_times.append(now)
        if is_half_open_probe or len(self._failure_times) >= 5:
            self._circuit_open_until = now + 30.0
        self._half_open_probe_in_flight = False

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=2.0, read=5.0, write=5.0, pool=2.0)
            )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        settings = get_settings()
        if not settings.NUTRITION_INTERNAL_SERVICE_TOKEN:
            raise NutritionAgentError()
        await self.start()
        is_half_open_probe = self._before_request()
        headers = {"X-Internal-Service-Token": settings.NUTRITION_INTERNAL_SERVICE_TOKEN}
        if current_request_id := request_id.get():
            headers["X-Request-ID"] = current_request_id

        for attempt in range(2):
            try:
                response = await self._client.request(
                    method,
                    f"{settings.NUTRITION_AGENT_URL.rstrip('/')}{path}",
                    json=json,
                    params=params,
                    headers=headers,
                )
            except httpx.HTTPError as error:
                qualifying_failure = self._is_qualifying_exception(error)
                if (
                    qualifying_failure
                    and attempt == 0
                    and self._is_retryable_method(method)
                ):
                    await asyncio.sleep(random.uniform(0.0, 0.25))
                    continue
                if qualifying_failure:
                    self._record_qualifying_failure(is_half_open_probe)
                elif is_half_open_probe:
                    self._half_open_probe_in_flight = False
                raise NutritionAgentError() from error

            qualifying_failure = self._is_qualifying_response(response)
            if (
                qualifying_failure
                and attempt == 0
                and self._is_retryable_method(method)
            ):
                await asyncio.sleep(random.uniform(0.0, 0.25))
                continue
            if qualifying_failure:
                self._record_qualifying_failure(is_half_open_probe)
            else:
                self._record_success()
            break

        if response.status_code >= 500:
            raise NutritionAgentError()
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail") if response.content else None
            except ValueError:
                detail = None
            if isinstance(detail, dict):
                raise NutritionAgentError(
                    response.status_code, detail.get("code"), detail.get("message")
                )
            if response.status_code == 422 and (message := validation_error_message(detail)):
                raise NutritionAgentError(422, "VALIDATION_ERROR", message)
            raise NutritionAgentError(response.status_code)
        return None if response.status_code == 204 else response.json()

    async def request_for_user(
        self,
        method: str,
        user_id: int,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Call an ownership-scoped private route for an authenticated user."""
        if isinstance(user_id, bool) or user_id <= 0:
            raise ValueError("Nutrition user ID must be a positive integer")
        if not path.startswith("/"):
            raise ValueError("Nutrition route path must start with '/'")
        return await self.request(
            method,
            f"/v1/nutrition/users/{user_id}{path}",
            json=json,
            params=params,
        )

    async def search_foods(
        self, query: str, limit: int, include_usda: bool
    ) -> dict[str, Any]:
        """Search shared nutrition reference data through the private service."""
        return await self.request(
            "GET",
            "/v1/nutrition/foods",
            params={"q": query, "limit": limit, "include_usda": include_usda},
        )

    async def get_food(self, fdc_id: int) -> dict[str, Any]:
        """Read one shared nutrition reference item through the private service."""
        if isinstance(fdc_id, bool) or fdc_id <= 0:
            raise ValueError("FDC ID must be a positive integer")
        return await self.request("GET", f"/v1/nutrition/foods/{fdc_id}")

    async def get_profile(self, user_id: int) -> dict[str, Any]:
        return await self.request_for_user("GET", user_id, "/profile")

    async def upsert_profile(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request_for_user("PUT", user_id, "/profile", json=payload)

    async def delete_profile(self, user_id: int) -> None:
        await self.request_for_user("DELETE", user_id, "/profile")

    async def create_meal_log(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request_for_user("POST", user_id, "/meal-logs", json=payload)

    async def list_meal_logs(
        self, user_id: int, params: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.request_for_user("GET", user_id, "/meal-logs", params=params)

    async def get_meal_log(self, user_id: int, meal_id: int) -> dict[str, Any]:
        return await self.request_for_user("GET", user_id, f"/meal-logs/{meal_id}")

    async def replace_meal_log(
        self, user_id: int, meal_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.request_for_user("PUT", user_id, f"/meal-logs/{meal_id}", json=payload)

    async def delete_meal_log(self, user_id: int, meal_id: int) -> None:
        await self.request_for_user("DELETE", user_id, f"/meal-logs/{meal_id}")

    async def calculate_targets(
        self, user_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.request_for_user("POST", user_id, "/targets/calculate", json=payload)

    async def save_target(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request_for_user("POST", user_id, "/targets", json=payload)

    async def get_current_target(
        self, user_id: int, target_date: str | None
    ) -> dict[str, Any]:
        params = {"date": target_date} if target_date else None
        return await self.request_for_user("GET", user_id, "/targets/current", params=params)

    async def get_history(self, user_id: int, params: dict[str, Any]) -> dict[str, Any]:
        return await self.request_for_user("GET", user_id, "/history", params=params)

    async def get_assessment_history(
        self, user_id: int, params: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.request_for_user("GET", user_id, "/assessment-history", params=params)

    async def generate_meal_plan(
        self, user_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self.request_for_user("POST", user_id, "/meal-plans", json=payload)

    async def evaluate(
        self,
        user_id: int,
        message: str,
        safety_context: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": message}
        if safety_context is not None:
            payload["safety_context"] = safety_context
        if profile is not None:
            payload["profile"] = profile
        return await self.request_for_user("POST", user_id, "/evaluate", json=payload)

    async def evaluate_stream(
        self, user_id: int, message: str, safety_context: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield validated private Nutrition SSE events through the dependency boundary."""
        settings = get_settings()
        payload: dict[str, Any] = {"message": message}
        if safety_context is not None:
            payload["safety_context"] = safety_context
        if profile is not None:
            payload["profile"] = profile
        if self._client is None:
            await self.start()
        assert self._client is not None
        probe = self._before_request()
        headers = {"X-Internal-Service-Token": settings.NUTRITION_INTERNAL_SERVICE_TOKEN}
        if correlation_id := request_id.get():
            headers["X-Request-ID"] = correlation_id
        request = self._client.build_request("POST", f"{settings.NUTRITION_AGENT_URL.rstrip('/')}/v1/nutrition/users/{user_id}/evaluate/stream", json=payload, headers=headers)
        response: httpx.Response | None = None
        complete = False
        try:
            response = await self._client.send(request, stream=True)
            if response.status_code >= 400:
                if self._is_qualifying_response(response):
                    self._record_qualifying_failure(probe)
                else:
                    self._half_open_probe_in_flight = False
                raise NutritionAgentError(response.status_code)
            event = "message"
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event = line.removeprefix("event:").strip()
                    continue
                if not line.startswith("data:"):
                    continue
                try:
                    data = json.loads(line.removeprefix("data:").strip())
                except json.JSONDecodeError as error:
                    raise NutritionAgentError(code="NUTRITION_STREAM_INVALID") from error
                if not isinstance(data, dict):
                    raise NutritionAgentError(code="NUTRITION_STREAM_INVALID")
                if event == "token":
                    token = data.get("token")
                    if not isinstance(token, str) or not token:
                        raise NutritionAgentError(code="NUTRITION_STREAM_INVALID")
                    yield {"type": "token", "token": token}
                elif event == "complete":
                    if not isinstance(data.get("message"), str):
                        raise NutritionAgentError(code="NUTRITION_STREAM_INVALID")
                    complete = True
                    self._record_success()
                    yield {"type": "complete", "assessment": data}
                elif event == "error":
                    raise NutritionAgentError(code=str(data.get("code") or "NUTRITION_STREAM_FAILED"))
                event = "message"
            if not complete:
                raise NutritionAgentError(code="NUTRITION_STREAM_INCOMPLETE")
        except httpx.HTTPError as error:
            if self._is_qualifying_exception(error):
                self._record_qualifying_failure(probe)
            else:
                self._half_open_probe_in_flight = False
            raise NutritionAgentError() from error
        finally:
            if response is not None:
                await response.aclose()

    async def evaluate_stream(
        self,
        user_id: int,
        message: str,
        safety_context: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield validated private Nutrition SSE events through the dependency boundary."""
        settings = get_settings()
        payload: dict[str, Any] = {"message": message}
        if safety_context is not None:
            payload["safety_context"] = safety_context
        if profile is not None:
            payload["profile"] = profile
        if self._client is None:
            await self.start()
        assert self._client is not None

        probe = self._before_request()
        headers = {"X-Internal-Service-Token": settings.NUTRITION_INTERNAL_SERVICE_TOKEN}
        if correlation_id := request_id.get():
            headers["X-Request-ID"] = correlation_id
        request = self._client.build_request(
            "POST",
            f"{settings.NUTRITION_AGENT_URL.rstrip('/')}/v1/nutrition/users/{user_id}/evaluate/stream",
            json=payload,
            headers=headers,
        )
        response: httpx.Response | None = None
        complete = False
        try:
            response = await self._client.send(request, stream=True)
            if response.status_code >= 400:
                if self._is_qualifying_response(response):
                    self._record_qualifying_failure(probe)
                else:
                    self._half_open_probe_in_flight = False
                detail: Any = None
                try:
                    detail = response.json().get("detail")
                except (ValueError, AttributeError):
                    pass
                raise NutritionAgentError(
                    response.status_code,
                    "VALIDATION_ERROR" if response.status_code == 422 else None,
                    validation_error_message(detail),
                )

            event = "message"
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event = line.removeprefix("event:").strip()
                    continue
                if not line.startswith("data:"):
                    continue
                try:
                    data = json.loads(line.removeprefix("data:").strip())
                except json.JSONDecodeError as error:
                    raise NutritionAgentError(code="NUTRITION_STREAM_INVALID") from error
                if not isinstance(data, dict):
                    raise NutritionAgentError(code="NUTRITION_STREAM_INVALID")
                if event == "token":
                    token = data.get("token")
                    if not isinstance(token, str) or not token:
                        raise NutritionAgentError(code="NUTRITION_STREAM_INVALID")
                    yield {"type": "token", "token": token}
                elif event == "complete":
                    if not isinstance(data.get("message"), str):
                        raise NutritionAgentError(code="NUTRITION_STREAM_INVALID")
                    complete = True
                    self._record_success()
                    yield {"type": "complete", "assessment": data}
                elif event == "error":
                    raise NutritionAgentError(code=str(data.get("code") or "NUTRITION_STREAM_FAILED"))
                event = "message"
            if not complete:
                raise NutritionAgentError(code="NUTRITION_STREAM_INCOMPLETE")
        except httpx.HTTPError as error:
            if self._is_qualifying_exception(error):
                self._record_qualifying_failure(probe)
            else:
                self._half_open_probe_in_flight = False
            raise NutritionAgentError() from error
        finally:
            if response is not None:
                await response.aclose()


nutrition_agent_client = NutritionAgentClient()