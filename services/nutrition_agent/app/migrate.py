"""Entrypoint used by the one-off Nutrition ECS migration task."""

import asyncio
from pathlib import Path

from .database import _session_factory, close_db
from .migration_runner import run_versioned_migrations


async def main() -> None:
    _session_factory()
    from . import database

    await run_versioned_migrations(
        database.engine,
        Path(__file__).parent / "db" / "migrations",
        "macoach-nutrition",
    )
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
