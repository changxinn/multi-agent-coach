"""Client for the private Nutrition Agent microservice."""
import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class NutritionAgentClient:
    """Synchronous client used inside the LangGraph worker thread."""

    def evaluate(self, user_id: int, message: str, profile: dict[str, Any]) -> dict[str, Any]:
        """Call nutrition agent microservice for evaluation."""
        settings = get_settings()
        if not settings.INTERNAL_SERVICE_TOKEN:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required for the Nutrition Agent service")

        response = httpx.post(
            f"{settings.NUTRITION_AGENT_URL.rstrip('/')}/v1/nutrition/evaluate",
            headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
            json={"user_id": user_id, "message": message, "profile": profile},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()


nutrition_agent_client = NutritionAgentClient()
