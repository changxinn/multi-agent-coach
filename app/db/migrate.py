"""Entrypoint used by the one-off API ECS migration task."""

import asyncio
from pathlib import Path

from app.db.database import close_db, engine
from app.db.migration_runner import run_versioned_migrations


async def main() -> None:
    await run_versioned_migrations(
        engine, Path(__file__).parent / "migrations", "macoach-api"
    )
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
