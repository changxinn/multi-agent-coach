from unittest.mock import AsyncMock, Mock

import pytest

from services.nutrition_agent.app import migrations
from services.nutrition_agent.app.migrations import (
    imported_food_cache_seed_exists,
    run_migrations,
    split_sql_statements,
)


def test_split_sql_statements_preserves_semicolons_in_sql_string_literals():
    statements = split_sql_statements(
        "INSERT INTO nutrition_food_cache (description, raw_response) "
        "VALUES ('Beans; cooked', '{\"note\":\"a; b\"}'::jsonb); "
        "SELECT 1;"
    )

    assert statements == [
        (
            "INSERT INTO nutrition_food_cache (description, raw_response) "
            "VALUES ('Beans; cooked', '{\"note\":\"a; b\"}'::jsonb);"
        ),
        "SELECT 1;",
    ]


def test_split_sql_statements_preserves_escaped_sql_quotes():
    statements = split_sql_statements("INSERT INTO foods VALUES ('Farmer''s; market');")

    assert statements == ["INSERT INTO foods VALUES ('Farmer''s; market');"]


@pytest.mark.asyncio
async def test_imported_food_cache_seed_exists_when_sentinel_is_present():
    connection = AsyncMock()
    result = Mock()
    result.scalar_one.return_value = True
    connection.exec_driver_sql.return_value = result

    assert (
        await imported_food_cache_seed_exists(
            connection, "003_seed_nutrition_food_cache.sql"
        )
        is True
    )
    connection.exec_driver_sql.assert_awaited_once()
    assert (
        "provider_food_id = '170178'" in connection.exec_driver_sql.await_args.args[0]
    )


@pytest.mark.asyncio
async def test_imported_food_cache_seed_does_not_exist_without_sentinel():
    connection = AsyncMock()
    result = Mock()
    result.scalar_one.return_value = False
    connection.exec_driver_sql.return_value = result

    assert (
        await imported_food_cache_seed_exists(
            connection, "003_seed_nutrition_food_cache.sql"
        )
        is False
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("seed_name", "provider_food_id"),
    [
        ("004_seed_nutrition_food_cache.sql", "2705967"),
        ("005_seed_nutrition_food_cache.sql", "170007"),
    ],
)
async def test_later_imported_food_cache_seeds_use_their_own_sentinels(
    seed_name, provider_food_id
):
    connection = AsyncMock()
    result = Mock()
    result.scalar_one.return_value = True
    connection.exec_driver_sql.return_value = result

    assert await imported_food_cache_seed_exists(connection, seed_name) is True
    assert (
        f"provider_food_id = '{provider_food_id}'"
        in connection.exec_driver_sql.await_args.args[0]
    )


@pytest.mark.asyncio
async def test_run_migrations_skips_imported_seed_before_reading_its_contents(
    monkeypatch, tmp_path
):
    migration_dir = tmp_path.parent / "db" / "migrations"
    migration_dir.mkdir(parents=True)
    seed = migration_dir / "005_seed_nutrition_food_cache.sql"
    seed.write_text("this is intentionally not valid SQL", encoding="utf-8")

    connection = AsyncMock()
    result = Mock()
    result.scalar_one.return_value = True
    connection.exec_driver_sql.return_value = result

    class Transaction:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    class Engine:
        def begin(self):
            return Transaction()

    monkeypatch.setattr(migrations, "Path", lambda _: tmp_path)

    await run_migrations(Engine())

    connection.exec_driver_sql.assert_awaited_once()
