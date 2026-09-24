"""Service-owned, idempotent migration runner for the Nutrition database."""

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger("uvicorn.error")
IMPORTED_FOOD_CACHE_SEEDS = {
    "003_seed_nutrition_food_cache.sql": ("usda", "170178"),
    "004_seed_nutrition_food_cache.sql": ("usda", "2709972"),
}


def split_sql_statements(content: str) -> list[str]:
    """Split SQL on statement delimiters outside single-quoted literals."""
    statements: list[str] = []
    statement: list[str] = []
    in_single_quote = False
    index = 0

    while index < len(content):
        character = content[index]
        statement.append(character)

        if character == "'":
            if (
                in_single_quote
                and index + 1 < len(content)
                and content[index + 1] == "'"
            ):
                statement.append(content[index + 1])
                index += 1
            else:
                in_single_quote = not in_single_quote
        elif character == ";" and not in_single_quote:
            sql = "".join(statement).strip()
            if sql:
                statements.append(sql)
            statement = []
        index += 1

    trailing_sql = "".join(statement).strip()
    if trailing_sql:
        statements.append(trailing_sql)
    return statements


async def imported_food_cache_seed_exists(connection, seed_name: str) -> bool:
    """Return whether a large imported food-cache seed is already present."""
    provider, provider_food_id = IMPORTED_FOOD_CACHE_SEEDS[seed_name]
    result = await connection.exec_driver_sql(
        f"""
        SELECT EXISTS (
            SELECT 1
            FROM nutrition_food_cache
            WHERE provider = '{provider}' AND provider_food_id = '{provider_food_id}'
        )
        """
    )
    return bool(result.scalar_one())


async def run_migrations(engine: AsyncEngine) -> None:
    """Apply Nutrition Agent SQL files in lexical order to its own database."""
    migration_dir = Path(__file__).parent / "db" / "migrations"
    migration_files = sorted(migration_dir.glob("*.sql"))
    if not migration_files:
        raise RuntimeError(f"No Nutrition Agent migrations found in {migration_dir}")

    logger.info("Applying %d Nutrition database migration(s)", len(migration_files))
    async with engine.begin() as connection:
        for migration_file in migration_files:
            if (
                migration_file.name in IMPORTED_FOOD_CACHE_SEEDS
                and await imported_food_cache_seed_exists(
                    connection, migration_file.name
                )
            ):
                logger.info(
                    "Skipping Nutrition migration %s; imported food-cache sentinel exists",
                    migration_file.name,
                )
                continue
            logger.info("Executing Nutrition migration: %s", migration_file.name)
            content = migration_file.read_text(encoding="utf-8-sig")
            statements = split_sql_statements(
                " ".join(
                    line.strip()
                    for line in content.splitlines()
                    if line.strip() and not line.strip().startswith("--")
                )
            )
            for statement in statements:
                await connection.exec_driver_sql(statement)
    logger.info("Nutrition database migration runner completed")
