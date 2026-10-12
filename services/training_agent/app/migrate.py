"""Entrypoint used by the one-off Training ECS migration task."""

import asyncio
from pathlib import Path

from . import database
from .migration_runner import run_versioned_migrations


async def main() -> None:
    database.session_factory()
    await run_versioned_migrations(
        database.engine, Path(__file__).parent / "db" / "migrations", "macoach-training"
    )
    await database.close_db()


if __name__ == "__main__":
    asyncio.run(main())
