"""PostgreSQL integration coverage for durable, authorized chat history."""
from __future__ import annotations

import asyncio
import os
import secrets

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.migrate import chat_history_test_database_url as isolated_test_database_url
from app.db.migrate import run_migrations
from app.services.chat_history_service import (
    ChatHistoryService,
    ChatSessionNotFoundError,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_durable_history_enforces_ownership_immutability_and_lifecycle() -> None:
    try:
        database_url = isolated_test_database_url()
    except RuntimeError as error:
        pytest.skip(str(error))

    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    engine = create_async_engine(database_url, pool_pre_ping=True)
    token = secrets.token_hex(8)
    try:
        result = await run_migrations()
        assert result.compatible, result.reason
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            owner_id = (await db.execute(text(
                "INSERT INTO systemdb.users (email, password, name) VALUES "
                "(:email, 'test', 'Chat Owner') RETURNING id"
            ), {"email": f"chat-owner-{token}@example.test"})).scalar_one()
            foreign_id = (await db.execute(text(
                "INSERT INTO systemdb.users (email, password, name) VALUES "
                "(:email, 'test', 'Chat Foreign') RETURNING id"
            ), {"email": f"chat-foreign-{token}@example.test"})).scalar_one()
            await db.commit()

            history = ChatHistoryService(db)
            session = await history.create_session(owner_id)
            chat_session_id = session.id
            session_identifier = session.session_id
            view = await history.build_view(owner_id, session_identifier, {})
            await history.append_user_message(view, "first durable message")
            await history.append_assistant_message(view, "first durable response", "Coach", {"safe": True})
            await db.commit()

            # Re-instantiation models a worker restart; persisted order survives it.
            recovered = await ChatHistoryService(db).build_view(owner_id, session_identifier, {})
            assert [message["content"] for message in recovered.messages] == [
                "first durable message", "first durable response"
            ]
            assert recovered.record.next_sequence == 3

            with pytest.raises(ChatSessionNotFoundError):
                await history.build_view(foreign_id, session_identifier, {})
            with pytest.raises(ChatSessionNotFoundError):
                await history.clear(foreign_id, session_identifier)

            with pytest.raises(DBAPIError):
                await db.execute(text(
                    "UPDATE systemdb.chat_messages SET content = 'mutated' "
                    "WHERE session_id = :session_id AND sequence = 1"
                ), {"session_id": chat_session_id})
            await db.rollback()

            with pytest.raises(DBAPIError):
                await db.execute(text(
                    "DELETE FROM systemdb.chat_messages "
                    "WHERE session_id = :session_id AND sequence = 1"
                ), {"session_id": chat_session_id})
            await db.rollback()

            with pytest.raises(IntegrityError):
                await db.execute(text(
                    "INSERT INTO systemdb.chat_messages "
                    "(session_id, sequence, role, content) VALUES (:session_id, 1, 'user', 'duplicate')"
                ), {"session_id": chat_session_id})
            await db.rollback()

            await history.clear(owner_id, session_identifier)
            await db.commit()
            assert (await history.build_view(owner_id, session_identifier, {})).messages == []

            await history.delete(owner_id, session_identifier)
            await db.commit()
            with pytest.raises(ChatSessionNotFoundError):
                await history.build_view(owner_id, session_identifier, {})

            await db.execute(text("DELETE FROM systemdb.users WHERE id IN (:owner, :foreign)"), {
                "owner": owner_id, "foreign": foreign_id
            })
            await db.commit()
    finally:
        await engine.dispose()
        if original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_database_url
        get_settings.cache_clear()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_chat_appends_allocate_distinct_sequences() -> None:
    try:
        database_url = isolated_test_database_url()
    except RuntimeError as error:
        pytest.skip(str(error))

    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    engine = create_async_engine(database_url, pool_pre_ping=True)
    token = secrets.token_hex(8)
    try:
        assert (await run_migrations()).compatible
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as setup_db:
            owner_id = (
                await setup_db.execute(
                    text(
                        "INSERT INTO systemdb.users (email, password, name) VALUES "
                        "(:email, 'test', 'Concurrent Owner') RETURNING id"
                    ),
                    {"email": f"chat-concurrent-{token}@example.test"},
                )
            ).scalar_one()
            session = await ChatHistoryService(setup_db).create_session(owner_id)
            session_identifier = session.session_id
            await setup_db.commit()

        async def append(content: str) -> None:
            async with factory() as db:
                history = ChatHistoryService(db)
                view = await history.build_view(owner_id, session_identifier, {})
                await history.append_user_message(view, content)

        await asyncio.gather(append("first concurrent message"), append("second concurrent message"))
        async with factory() as verify_db:
            sequences = list(
                (
                    await verify_db.execute(
                        text(
                            "SELECT sequence FROM systemdb.chat_messages "
                            "WHERE session_id = (SELECT id FROM systemdb.chat_sessions WHERE session_id = :session_id) "
                            "ORDER BY sequence"
                        ),
                        {"session_id": session_identifier},
                    )
                ).scalars()
            )
            assert sequences == [1, 2]
            await verify_db.execute(text("DELETE FROM systemdb.users WHERE id = :owner"), {"owner": owner_id})
            await verify_db.commit()
    finally:
        await engine.dispose()
        if original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_database_url
        get_settings.cache_clear()