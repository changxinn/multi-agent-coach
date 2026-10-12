"""Deployment seeds once after successful API migrations."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db import migrate


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
async def test_migration_seeds_only_when_enabled_and_closes_database(
    monkeypatch, enabled
):
    config = SimpleNamespace(SEED_DEMO_USERS=enabled)
    session = object()
    order = []

    @asynccontextmanager
    async def session_factory():
        yield session

    async def migrations(*args):
        order.append("migrate")

    async def seed(*args):
        order.append("seed")

    seed_mock = AsyncMock(side_effect=seed)
    close_mock = AsyncMock()
    monkeypatch.setattr(migrate, "get_settings", lambda: config)
    monkeypatch.setattr(migrate, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(migrate, "run_versioned_migrations", migrations)
    monkeypatch.setattr(migrate, "seed_demo_users", seed_mock)
    monkeypatch.setattr(migrate, "close_db", close_mock)

    await migrate.main()

    assert order == (["migrate", "seed"] if enabled else ["migrate"])
    if enabled:
        seed_mock.assert_awaited_once_with(session, config)
    close_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_migration_skips_seed_and_still_closes_database(monkeypatch):
    seed = AsyncMock()
    close = AsyncMock()
    monkeypatch.setattr(
        migrate,
        "run_versioned_migrations",
        AsyncMock(side_effect=RuntimeError("failed")),
    )
    monkeypatch.setattr(migrate, "seed_demo_users", seed)
    monkeypatch.setattr(migrate, "close_db", close)
    with pytest.raises(RuntimeError, match="failed"):
        await migrate.main()
    seed.assert_not_awaited()
    close.assert_awaited_once()
