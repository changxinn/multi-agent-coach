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