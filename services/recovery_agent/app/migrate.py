"""Entrypoint used by the one-off Recovery ECS migration task."""

import asyncio

from .config import settings
from .repository import RecoveryRepository


async def main() -> None:
    repository = RecoveryRepository(settings)
    await repository.connect()
    try:
        # Recovery's schema is currently code-defined; retain the same controlled
        # idempotent DDL under an advisory lock and record a deployment version.
        async with repository._pool.acquire() as connection:
            await connection.execute(
                "SELECT pg_advisory_lock(hashtext('macoach-recovery'))"
            )
            try:
                await repository.ensure_schema()
            finally:
                await connection.execute(
                    "SELECT pg_advisory_unlock(hashtext('macoach-recovery'))"
                )
    finally:
        await repository.close()


if __name__ == "__main__":
    asyncio.run(main())
