"""Build bounded, server-assembled specialist context from durable history."""
from __future__ import annotations

from typing import Any

from app.db.repositories.chat_history_repo import ChatHistoryRepository

CONTEXT_MESSAGE_LIMIT = 24


class ChatContextBuilder:
    """The sole builder for specialist chat-history payloads."""

    def __init__(self, repository: ChatHistoryRepository) -> None:
        self.repository = repository

    async def build(self, view: Any) -> dict[str, Any]:
        boundary = max(view.record.history_start_sequence, view.record.summary_through_sequence)
        messages = await self.repository.messages_after(view.record, boundary, CONTEXT_MESSAGE_LIMIT)
        return {
            "version": "chat-history-v1",
            "summary": view.record.summary,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
        }