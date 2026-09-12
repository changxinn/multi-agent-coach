"""Durable chat lifecycle, safe transcript views, and bounded graph context."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import ChatSession, ChatTurn
from app.db.repositories.chat_history_repo import ChatHistoryRepository
from app.services.chat_context_builder import ChatContextBuilder
from app.services.chat_summary_service import ChatSummaryService

CONTEXT_MESSAGE_LIMIT = 24


class ChatSessionNotFoundError(ValueError):
    """The caller does not own an active session with this id."""


class ChatTurnConflictError(ValueError):
    """An idempotency key is processing or is bound to different content."""


@dataclass
class ChatSessionView:
    """Graph-compatible, server-built session view rather than client history."""

    session_id: str
    user_id: int
    profile: dict[str, Any]
    messages: list[dict[str, Any]]
    record: ChatSession


class ChatHistoryService:
    def __init__(self, db: AsyncSession, summary_service: ChatSummaryService | None = None) -> None:
        self.repository = ChatHistoryRepository(db)
        self.context_builder = ChatContextBuilder(self.repository)
        self.summary_service = summary_service or ChatSummaryService()

    async def create_session(self, user_id: int) -> ChatSession:
        # 128 bits of entropy, server-generated. Retry only an improbable collision.
        for _ in range(3):
            session = await self.repository.create_session(user_id, f"chat_{secrets.token_hex(16)}")
            return session
        raise RuntimeError("Unable to allocate a session identifier")

    async def get_session(self, user_id: int, session_id: str) -> ChatSession:
        session = await self.repository.get_owned_session(user_id, session_id)
        if session is None:
            raise ChatSessionNotFoundError("Session not found")
        return session

    async def build_view(
        self, user_id: int, session_id: str, profile: dict[str, Any]
    ) -> ChatSessionView:
        session = await self.get_session(user_id, session_id)
        messages = await self.repository.visible_messages(session, CONTEXT_MESSAGE_LIMIT)
        return ChatSessionView(
            session_id=session.session_id,
            user_id=user_id,
            profile=profile,
            messages=[self._message_dict(message) for message in messages],
            record=session,
        )

    async def append_user_message(self, view: ChatSessionView, content: str) -> None:
        record = await self._append_message(view.user_id, view.session_id, "user", content)
        view.messages.append(self._message_dict(record))

    async def nutrition_context(self, view: ChatSessionView) -> dict[str, Any]:
        """Return only bounded, server-assembled context for Nutrition."""
        return await self.context_builder.build(view)

    async def append_assistant_message(
        self, view: ChatSessionView, content: str, agent_name: str | None, metadata: dict[str, Any] | None
    ) -> None:
        record = await self._append_message(
            view.user_id, view.session_id, "assistant", content, agent_name, self._safe_metadata(metadata)
        )
        view.messages.append(self._message_dict(record))
        await self._roll_summary(view)

    async def clear(self, user_id: int, session_id: str) -> None:
        await self._end_existing_transaction()
        async with self.repository.db.begin():
            session = await self._locked_session(user_id, session_id)
            await self.repository.clear_history(session)

    async def delete(self, user_id: int, session_id: str) -> None:
        await self._end_existing_transaction()
        async with self.repository.db.begin():
            session = await self._locked_session(user_id, session_id)
            await self.repository.soft_delete(session)

    async def details(self, user_id: int, session_id: str, profile: dict[str, Any]) -> ChatSessionView:
        return await self.build_view(user_id, session_id, profile)

    async def _roll_summary(self, view: ChatSessionView) -> None:
        interval_messages = get_settings().CHAT_SUMMARY_TURN_INTERVAL * 2
        eligible = await self.repository.messages_after(
            view.record,
            max(view.record.history_start_sequence, view.record.summary_through_sequence),
            interval_messages,
        )
        if len(eligible) < interval_messages:
            return
        await self._end_existing_transaction()
        summary = await self.summary_service.summarize(view.record.summary, eligible)
        if summary is not None:
            async with self.repository.db.begin():
                session = await self._locked_session(view.user_id, view.session_id)
                await self.repository.set_summary(session, summary, eligible[-1].sequence)
                view.record = session

    async def claim_turn(
        self, user_id: int, session_id: str, idempotency_key: str, request_fingerprint: str, content: str
    ) -> tuple[ChatSessionView, ChatTurn, bool]:
        """Atomically claim a turn or return its completed replay state."""
        await self._end_existing_transaction()
        async with self.repository.db.begin():
            session = await self._locked_session(user_id, session_id)
            turn = await self.repository.get_turn_for_update(session, idempotency_key)
            if turn is not None:
                if turn.request_fingerprint != request_fingerprint:
                    raise ChatTurnConflictError("Idempotency key was used with different request content")
                if turn.status == "completed":
                    return await self._view_for_record(user_id, {}, session), turn, False
                if turn.status == "processing":
                    raise ChatTurnConflictError("A request with this idempotency key is still processing")
                turn.status = "processing"
                turn.response_text = None
                turn.response_metadata = None
                turn.completed_at = None
                turn.updated_at = datetime.now(UTC)
            else:
                turn = await self.repository.create_turn(session, idempotency_key, request_fingerprint)
            record = await self.repository.append_message(session, "user", content)
            view = await self._view_for_record(user_id, {}, session)
            view.messages.append(self._message_dict(record))
            return view, turn, True

    async def complete_turn(
        self, user_id: int, session_id: str, idempotency_key: str, content: str, metadata: dict[str, Any] | None
    ) -> None:
        await self._end_existing_transaction()
        async with self.repository.db.begin():
            session = await self._locked_session(user_id, session_id)
            turn = await self.repository.get_turn_for_update(session, idempotency_key)
            if turn is None or turn.status != "processing":
                raise ChatTurnConflictError("Chat turn is not available for completion")
            record = await self.repository.append_message(
                session, "assistant", content, None, self._safe_metadata(metadata)
            )
            turn.status = "completed"
            turn.response_text = content
            turn.response_metadata = self._safe_metadata(metadata)
            turn.completed_at = datetime.now(UTC)
            turn.updated_at = datetime.now(UTC)
            await self.repository.db.flush()
        completed_view = await self._view_for_record(user_id, {}, session)
        completed_view.messages.append(self._message_dict(record))
        await self._roll_summary(completed_view)

    async def fail_turn(self, user_id: int, session_id: str, idempotency_key: str) -> None:
        await self._end_existing_transaction()
        async with self.repository.db.begin():
            session = await self._locked_session(user_id, session_id)
            turn = await self.repository.get_turn_for_update(session, idempotency_key)
            if turn is not None and turn.status == "processing":
                turn.status = "failed"
                turn.updated_at = datetime.now(UTC)
                await self.repository.db.flush()

    async def _append_message(
        self, user_id: int, session_id: str, role: str, content: str,
        agent_name: str | None = None, metadata: dict[str, Any] | None = None,
    ) -> Any:
        await self._end_existing_transaction()
        async with self.repository.db.begin():
            session = await self._locked_session(user_id, session_id)
            return await self.repository.append_message(session, role, content, agent_name, metadata)

    async def _locked_session(self, user_id: int, session_id: str) -> ChatSession:
        session = await self.repository.get_owned_session_for_update(user_id, session_id)
        if session is None:
            raise ChatSessionNotFoundError("Session not found")
        return session

    async def _view_for_record(
        self, user_id: int, profile: dict[str, Any], session: ChatSession
    ) -> ChatSessionView:
        messages = await self.repository.visible_messages(session, CONTEXT_MESSAGE_LIMIT)
        return ChatSessionView(
            session_id=session.session_id, user_id=user_id, profile=profile,
            messages=[self._message_dict(message) for message in messages], record=session,
        )

    async def _end_existing_transaction(self) -> None:
        """End implicit read transactions before an independently atomic mutation."""
        db = getattr(self.repository, "db", None)
        if db is not None and db.in_transaction():
            await db.commit()

    @staticmethod
    def _message_dict(message: Any) -> dict[str, Any]:
        result: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.agent_name:
            result["name"] = message.agent_name
        if message.message_metadata:
            result["metadata"] = message.message_metadata
        return result

    @staticmethod
    def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
        if not metadata:
            return {}
        # Persist only JSON-shaped response metadata generated by the server.
        return {key: value for key, value in metadata.items() if isinstance(key, str)}