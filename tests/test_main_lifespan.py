import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from app import main


@pytest.mark.asyncio
@pytest.mark.parametrize("seed_enabled", [False, True])
async def test_lifespan_initializes_and_closes_resources(monkeypatch, seed_enabled):
    cleanup_task = asyncio.create_task(asyncio.sleep(60))
    session = AsyncMock()

    @asynccontextmanager
    async def session_context():
        yield session

    monkeypatch.setattr(main.settings, "SEED_DEMO_USERS", seed_enabled)
    monkeypatch.setattr(main, "init_db", AsyncMock())
    monkeypatch.setattr(main, "close_db", AsyncMock())
    monkeypatch.setattr(main, "seed_demo_users", AsyncMock())
    monkeypatch.setattr(main, "AsyncSessionLocal", session_context)
    monkeypatch.setattr(
        main.session_manager, "start_cleanup_task", AsyncMock(return_value=cleanup_task)
    )

    async with main.lifespan(main.app):
        pass

    main.init_db.assert_awaited_once()
    main.close_db.assert_awaited_once()
    assert cleanup_task.cancelled()
    if seed_enabled:
        main.seed_demo_users.assert_awaited_once_with(session, main.settings)
    else:
        main.seed_demo_users.assert_not_awaited()


@pytest.mark.asyncio
async def test_root_and_health_endpoints_return_application_metadata():
    assert (await main.health_check())["status"] == "healthy"
    assert (await main.root())["docs"] == "/docs"
