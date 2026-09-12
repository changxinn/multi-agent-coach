"""Compatibility session view for legacy direct orchestrator callers.

Durable API sessions and transcripts are exclusively owned by PostgreSQL through
``ChatHistoryService``. This module deliberately has no storage, expiry, Redis,
or S3 behavior.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class Session:
    """In-process value object retained only for legacy non-API callers."""

    def __init__(self, session_id: str, user_id: int, profile: dict[str, Any]):
        self.session_id = session_id
        self.user_id = user_id
        self.profile = profile
        self.messages: list[dict[str, Any]] = []
        self.created_at = datetime.now(UTC)
        self.last_activity = datetime.now(UTC)
        self.agent_state: dict[str, Any] = {}


class SessionManager:
    """Removed durable-path manager retained as an explicit non-persistent shim."""

    async def create_session(
        self, user_id: int, profile: dict[str, Any], session_id: str | None = None
    ) -> Session:
        if session_id is None:
            raise RuntimeError("Durable sessions must be created through ChatHistoryService")
        return Session(session_id, user_id, profile)


session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """Return the legacy non-persistent compatibility shim."""
    return session_manager