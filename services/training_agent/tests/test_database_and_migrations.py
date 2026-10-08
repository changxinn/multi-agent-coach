from unittest.mock import AsyncMock, Mock

import pytest

from services.training_agent.app import config, database, migrations


def test_session_factory_requires_database_url(monkeypatch):
    monkeypatch.setattr(database, "SessionLocal", None)
    monkeypatch.setattr(database.settings, "DATABASE_URL", "")

    with pytest.raises(RuntimeError, match="TRAINING_DATABASE_URL"):
        database.session_factory()


def test_session_factory_normalizes_postgres_url_and_reuses_factory(monkeypatch):
    engine = Mock()
    factory = Mock()
    create_engine = Mock(return_value=engine)
    create_factory = Mock(return_value=factory)
    monkeypatch.setattr(database, "engine", None)
    monkeypatch.setattr(database, "SessionLocal", None)
    monkeypatch.setattr(database.settings, "DATABASE_URL", "postgresql://db/training")
    monkeypatch.setattr(database, "create_async_engine", create_engine)
    monkeypatch.setattr(database, "async_sessionmaker", create_factory)

    assert database.session_factory() is factory
    assert database.session_factory() is factory
    create_engine.assert_called_once_with(
        "postgresql+asyncpg://db/training", pool_pre_ping=True
    )


@pytest.mark.asyncio
async def test_get_db_commits_and_rolls_back(monkeypatch):
    session = AsyncMock()

    class SessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_):
            return False

    monkeypatch.setattr(database, "session_factory", lambda: lambda: SessionContext())
    generator = database.get_db()
    assert await anext(generator) is session
    with pytest.raises(StopAsyncIteration):
        await anext(generator)
    session.commit.assert_awaited_once()

    generator = database.get_db()
    await anext(generator)
    with pytest.raises(RuntimeError):
        await generator.athrow(RuntimeError("rollback"))
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_init_and_close_database(monkeypatch):
    engine = AsyncMock()
    migrations_run = AsyncMock()
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "session_factory", Mock())
    monkeypatch.setattr(
        "services.training_agent.app.migrations.run_migrations", migrations_run
    )

    await database.init_db()
    migrations_run.assert_awaited_once_with(engine)
    await database.close_db()
    engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_migrations_executes_non_empty_statements(monkeypatch, tmp_path):
    migration_dir = tmp_path / "db" / "migrations"
    migration_dir.mkdir(parents=True)
    (migration_dir / "002.sql").write_text("SELECT 2; ;", encoding="utf-8")
    (migration_dir / "001.sql").write_text("SELECT 1;", encoding="utf-8")
    connection = AsyncMock()

    class ConnectionContext:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, *_):
            return False

    engine = Mock(begin=Mock(return_value=ConnectionContext()))
    monkeypatch.setattr(migrations, "Path", lambda *_: tmp_path / "migrations.py")

    await migrations.run_migrations(engine)

    assert [
        call.args[0].strip() for call in connection.exec_driver_sql.await_args_list
    ] == [
        "SELECT 1",
        "SELECT 2",
    ]


def test_repository_root_falls_back_to_current_directory(monkeypatch, tmp_path):
    class CandidatePath:
        def resolve(self):
            return self

        @property
        def parents(self):
            return [tmp_path]

    class FakePath:
        def __new__(cls, *_):
            return CandidatePath()

        @staticmethod
        def cwd():
            return tmp_path

    monkeypatch.setattr(config, "Path", FakePath)

    assert config._repository_root() == tmp_path
