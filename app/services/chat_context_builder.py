"""Build bounded, server-assembled specialist context from durable history."""
from __future__ import annotations

from typing import Any

from app.db.repositories.chat_history_repo import ChatHistoryRepository

CONTEXT_MESSAGE_LIMIT = 24
RECENT_MEAL_RECOMMENDATION_LIMIT = 4
_MEAL_RECOMMENDATION_FIELDS = (
    "meal_type",
    "name",
    "description",
    "rationale",
    "calories",
    "protein_g",
    "carbs_g",
    "fiber_g",
    "fat_g",
    "satisfies",
    "target_percentages",
)
_REQUIRED_MEAL_RECOMMENDATION_FIELDS = {
    "meal_type",
    "name",
    "calories",
    "protein_g",
    "carbs_g",
    "fiber_g",
    "fat_g",
}


class ChatContextBuilder:
    """The sole builder for specialist chat-history payloads."""

    def __init__(self, repository: ChatHistoryRepository) -> None:
        self.repository = repository

    async def build(self, view: Any) -> dict[str, Any]:
        boundary = max(view.record.history_start_sequence, view.record.summary_through_sequence)
        messages = await self.repository.messages_after(view.record, boundary, CONTEXT_MESSAGE_LIMIT)
        recent_meal_recommendations = self._recent_meal_recommendations(messages)
        return {
            "version": "chat-history-v1",
            "summary": view.record.summary,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "recent_meal_recommendations": recent_meal_recommendations,
        }

    @staticmethod
    def _recent_meal_recommendations(messages: list[Any]) -> list[dict[str, Any]]:
        """Return the newest server-produced structured meal options, if valid.

        Assistant prose remains transcript context only. This separate field prevents
        follow-up recall from treating model-rendered prose as an authoritative source
        of ingredients or nutrition estimates.
        """
        for message in reversed(messages):
            metadata = getattr(message, "message_metadata", None)
            if getattr(message, "role", None) != "assistant" or not isinstance(metadata, dict):
                continue
            meals = metadata.get("meal_recommendations")
            if not isinstance(meals, list) or not 1 <= len(meals) <= RECENT_MEAL_RECOMMENDATION_LIMIT:
                continue
            if not all(
                isinstance(meal, dict)
                and _REQUIRED_MEAL_RECOMMENDATION_FIELDS.issubset(meal)
                for meal in meals
            ):
                continue
            return [
                {field: meal[field] for field in _MEAL_RECOMMENDATION_FIELDS if field in meal}
                for meal in meals
            ]
        return []