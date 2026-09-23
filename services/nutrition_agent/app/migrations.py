"""Service-owned, idempotent migration runner for the Nutrition database."""

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger("uvicorn.error")


async def run_migrations(engine: AsyncEngine) -> None:
    """Apply Nutrition Agent SQL files in lexical order to its own database."""
    migration_dir = Path(__file__).parent / "db" / "migrations"
    migration_files = sorted(migration_dir.glob("*.sql"))
    if not migration_files:
        raise RuntimeError(f"No Nutrition Agent migrations found in {migration_dir}")

    logger.info("Applying %d Nutrition database migration(s)", len(migration_files))
    async with engine.begin() as connection:
        for migration_file in migration_files:
            logger.info("Executing Nutrition migration: %s", migration_file.name)
            content = migration_file.read_text(encoding="utf-8-sig")
            statements = [
                statement.strip()
                for statement in " ".join(
                    line.strip()
                    for line in content.splitlines()
                    if line.strip() and not line.strip().startswith("--")
                ).split(";")
                if statement.strip()
            ]
            for statement in statements:
                await connection.exec_driver_sql(statement)
    logger.info("Nutrition database migration runner completed")