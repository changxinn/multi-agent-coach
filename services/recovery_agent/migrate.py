"""Controlled Recovery Agent schema initialization entry point."""

import asyncio

from app.repository import RecoveryRepository

from app.config import settings


async def migrate() -> None:
    repository = RecoveryRepository(settings)
    await repository.connect()
    await repository.close()


if __name__ == "__main__":
    asyncio.run(migrate())
