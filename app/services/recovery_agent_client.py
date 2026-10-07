"""Client for the private Recovery Agent microservice."""

import logging
from datetime import datetime
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class RecoveryAgentClient:
    """Synchronous client used inside the LangGraph worker thread."""

    def evaluate(
        self, user_id: int, message: str, profile: dict[str, Any]
    ) -> dict[str, Any]:
        settings = get_settings()
        if not settings.INTERNAL_SERVICE_TOKEN:
            raise RuntimeError(
                "INTERNAL_SERVICE_TOKEN is required for the Recovery Agent service"
            )

        response = httpx.post(
            f"{settings.RECOVERY_AGENT_URL.rstrip('/')}/v1/recovery/evaluate",
            headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
            json={"user_id": user_id, "message": message, "profile": profile},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    async def _request(self, method, path, **kwargs):
        settings = get_settings()
        if not settings.INTERNAL_SERVICE_TOKEN:
            raise RecoveryAgentUnavailableError("Internal token is required")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.request(
                    method,
                    settings.RECOVERY_AGENT_URL.rstrip("/") + "/v1/recovery/" + path,
                    headers={
                        "X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN
                    },
                    **kwargs,
                )
            if response.status_code in (404, 409, 422):
                raise RecoveryRecordError(
                    response.status_code, "Recovery record could not be saved or found"
                )
            response.raise_for_status()
            return response.json() if response.status_code != 204 else None
        except httpx.HTTPError as exc:
            raise RecoveryAgentUnavailableError(
                "Recovery service is unavailable"
            ) from exc

    @staticmethod
    def _record_path(resource, record_id=None):
        if resource not in ("sleep-logs", "check-ins", "assessments"):
            raise ValueError("Unknown recovery resource")
        return (
            "records/" + resource + (f"/{record_id}" if record_id is not None else "")
        )

    async def list_records(self, resource, page, page_size, user_id=None):
        params = {"page": page, "page_size": page_size}
        if user_id is not None:
            params["user_id"] = user_id
        return await self._request("GET", self._record_path(resource), params=params)

    async def write_record(self, resource, values, record_id=None):
        return await self._request(
            "PUT" if record_id is not None else "POST",
            self._record_path(resource, record_id),
            json=values,
        )

    async def delete_record(self, resource, record_id):
        return await self._request("DELETE", self._record_path(resource, record_id))

    async def dashboard_data(self, user_id, start_date, end_date):
        data = await self._request(
            "GET",
            f"dashboard/{user_id}",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )
        for value in data.values():
            for row in value if isinstance(value, list) else [value]:
                if row and isinstance(row.get("created_at"), str):
                    row["created_at"] = datetime.fromisoformat(row["created_at"])
        return data


class RecoveryRecordError(RuntimeError):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


class RecoveryAgentUnavailableError(RuntimeError):
    pass


recovery_agent_client = RecoveryAgentClient()
