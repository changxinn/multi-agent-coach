from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.db.database import _execute_migration_statement


@pytest.mark.asyncio
async def test_migration_execution_preserves_json_numeric_values():
    conn = AsyncMock()
    statement = (
        "INSERT INTO systemdb.nutrition_food_cache (raw_response) "
        "VALUES ('{\"fdcId\":321358}'::jsonb)"
    )

    await _execute_migration_statement(conn, statement)

    conn.exec_driver_sql.assert_awaited_once_with(statement)
    conn.execute.assert_not_awaited()


def test_shared_state_migration_upgrades_legacy_meal_item_columns_before_index():
    migration = (
        Path(__file__).parents[1]
        / "app/db/migrations/005_create_shared_state_tables.sql"
    ).read_text(encoding="utf-8")

    upgrade_statement = """ALTER TABLE systemdb.nutrition_meal_items
    ADD COLUMN IF NOT EXISTS food_provider VARCHAR(32),
    ADD COLUMN IF NOT EXISTS provider_food_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS nutrition_snapshot JSONB;"""
    provider_index = "CREATE INDEX IF NOT EXISTS nutrition_meal_items_provider_idx"

    assert upgrade_statement in migration
    assert migration.index(upgrade_statement) < migration.index(provider_index)
