"""Client for the private Recovery Agent microservice."""
import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class RecoveryAgentClient:
    """Synchronous client used inside the LangGraph worker thread."""

    def evaluate(self, user_id: int, message: str, profile: dict[str, Any]) -> dict[str, Any]:
        settings = get_settings()
        if not settings.INTERNAL_SERVICE_TOKEN:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for the Recovery Agent service")

        response = httpx.post(
            f"{settings.RECOVERY_AGENT_URL.rstrip('/')}/v1/recovery/evaluate",
            headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
            json={"user_id": user_id, "message": message, "profile": profile},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()


recovery_agent_client = RecoveryAgentClient()
