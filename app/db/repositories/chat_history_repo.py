"""Authorized persistence primitives for durable chat sessions and messages."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessageRecord, ChatSession, ChatTurn


class ChatHistoryRepository:
    """Database access layer; callers must supply the authenticated user id."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_session(self, user_id: int, session_id: str) -> ChatSession:
        session = ChatSession(session_id=session_id, user_id=user_id)
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_owned_session(self, user_id: int, session_id: str) -> ChatSession | None:
        result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id,
                ChatSession.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_owned_session_for_update(self, user_id: int, session_id: str) -> ChatSession | None:
        result = await self.db.execute(
            select(ChatSession)
            .where(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id,
                ChatSession.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_turn_for_update(self, session: ChatSession, idempotency_key: str) -> ChatTurn | None:
        result = await self.db.execute(
            select(ChatTurn)
            .where(ChatTurn.session_id == session.id, ChatTurn.idempotency_key == idempotency_key)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def create_turn(
        self, session: ChatSession, idempotency_key: str, request_fingerprint: str
    ) -> ChatTurn:
        turn = ChatTurn(
            session_id=session.id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            status="processing",
        )
        self.db.add(turn)
        await self.db.flush()
        return turn

    async def visible_messages(self, session: ChatSession, limit: int = 100) -> list[ChatMessageRecord]:
        result = await self.db.execute(
            select(ChatMessageRecord)
            .where(
                ChatMessageRecord.session_id == session.id,
                ChatMessageRecord.sequence > session.history_start_sequence,
            )
            .order_by(ChatMessageRecord.sequence.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def messages_after(
        self, session: ChatSession, sequence: int, limit: int
    ) -> list[ChatMessageRecord]:
        result = await self.db.execute(
            select(ChatMessageRecord)
            .where(
                ChatMessageRecord.session_id == session.id,
                ChatMessageRecord.sequence > sequence,
                ChatMessageRecord.sequence > session.history_start_sequence,
            )
            .order_by(ChatMessageRecord.sequence.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def append_message(
        self,
        session: ChatSession,
        role: str,
        content: str,
        agent_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessageRecord:
        sequence = session.next_sequence
        record = ChatMessageRecord(
            session_id=session.id,
            sequence=sequence,
            role=role,
            content=content,
            agent_name=agent_name,
            message_metadata=metadata or {},
        )
        session.next_sequence = sequence + 1
        session.updated_at = datetime.now(UTC)
        self.db.add(record)
        await self.db.flush()
        return record

    async def clear_history(self, session: ChatSession) -> None:
        # Keep immutable rows but move the user-visible/context boundary forward.
        session.history_start_sequence = session.next_sequence - 1
        session.summary = None
        session.summary_through_sequence = 0
        session.updated_at = datetime.now(UTC)
        await self.db.flush()

    async def soft_delete(self, session: ChatSession) -> None:
        session.deleted_at = datetime.now(UTC)
        session.summary = None
        session.updated_at = datetime.now(UTC)
        await self.db.flush()

    async def set_summary(self, session: ChatSession, summary: str, through_sequence: int) -> None:
        session.summary = summary
        session.summary_through_sequence = through_sequence
        session.updated_at = datetime.now(UTC)
        await self.db.flush()