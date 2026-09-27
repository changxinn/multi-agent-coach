"""
Database seeding utilities.
"""

import asyncio
import logging

from app.db.database import run_migrations

logger = logging.getLogger(__name__)


async def seed_database() -> None:
    """
    Main seeding function.

    Runs database migrations.
    """
    logger.info("Starting database seeding...")

    # Run migrations first
    await run_migrations()

    logger.info("Database seeding completed successfully")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(seed_database())
