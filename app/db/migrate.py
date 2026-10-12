"""Entrypoint used by the one-off API ECS migration task."""

import asyncio
from pathlib import Path

from app.config import get_settings
from app.db.database import AsyncSessionLocal, close_db, engine
from app.db.demo_seed import seed_demo_users
from app.db.migration_runner import run_versioned_migrations


async def main() -> None:
    try:
        await run_versioned_migrations(
            engine, Path(__file__).parent / "migrations", "macoach-api"
        )
        settings = get_settings()
        if settings.SEED_DEMO_USERS:
            async with AsyncSessionLocal() as db:
                await seed_demo_users(db, settings)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
