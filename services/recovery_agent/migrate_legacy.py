"""Explicit, non-destructive copy of legacy recovery records into recoverydb.

Run from the repository root: python -m services.recovery_agent.migrate_legacy
Set RECOVERY_LEGACY_DATABASE_URL and RECOVERY_DATABASE_URL before running.
Pause recovery writes and back up both databases before the copy.
"""

import asyncio
import os
import re

import asyncpg

from .app.config import Settings
from .app.repository import RECORD_COLUMNS, RecoveryRepository, record_dict


async def copy_records(source, destination, source_schema: str, target_schema: str):
    for schema in (source_schema, target_schema):
        if not re.fullmatch(r"[A-Za-z_]\w*", schema):
            raise ValueError("Invalid recovery schema")
    counts = {}
    async with (
        source.transaction(isolation="repeatable_read", readonly=True),
        destination.transaction(),
    ):
        await destination.execute("SELECT pg_advisory_xact_lock(812004)")
        # Block concurrent destination writes until every table has been copied.
        tables = [table for table, _ in RECORD_COLUMNS.values()]
        await destination.execute(
            "LOCK TABLE "
            + ", ".join(f'"{target_schema}".{t}' for t in tables)
            + " IN EXCLUSIVE MODE"
        )
        for table, columns in RECORD_COLUMNS.values():
            fields = ("id", *columns, "created_at")
            copied = 0
            async for row in source.cursor(
                f'SELECT {", ".join(fields)} FROM "{source_schema}".{table} ORDER BY id',
                prefetch=100,
            ):
                existing = await destination.fetchrow(
                    f'SELECT {", ".join(fields)} FROM "{target_schema}".{table} WHERE id = $1',
                    row["id"],
                )
                if existing is not None:
                    if record_dict(existing) != record_dict(row):
                        raise RuntimeError(
                            f"Conflicting {table} record ID {row['id']}; no records were overwritten"
                        )
                    continue
                placeholders = ", ".join(f"${i + 1}" for i in range(len(fields)))
                await destination.execute(
                    f'INSERT INTO "{target_schema}".{table} ({", ".join(fields)}) VALUES ({placeholders})',
                    *(row[f] for f in fields),
                )
                copied += 1
            counts[table] = copied
        for table in tables:
            await destination.execute(
                f"SELECT setval(pg_get_serial_sequence('\"{target_schema}\".{table}', 'id'), "
                f'COALESCE((SELECT MAX(id) FROM "{target_schema}".{table}), 1), '
                f'EXISTS(SELECT 1 FROM "{target_schema}".{table}))'
            )
    return counts


async def main():
    settings = Settings()
    source_url = os.getenv("RECOVERY_LEGACY_DATABASE_URL")
    if not source_url:
        raise RuntimeError(
            "RECOVERY_LEGACY_DATABASE_URL must explicitly name the legacy source"
        )
    repository = RecoveryRepository(settings)
    await repository.connect()
    source = None
    try:
        source = await asyncpg.connect(
            source_url.replace("postgresql+asyncpg://", "postgresql://")
        )
        async with repository._pool.acquire() as destination:
            counts = await copy_records(
                source,
                destination,
                os.getenv("RECOVERY_LEGACY_SCHEMA", "systemdb"),
                settings.validated_schema(),
            )
        print("Copied recovery records:", counts)
        print(
            "Legacy source records were retained. Repeating the copy skips identical records."
        )
    finally:
        if source is not None:
            await source.close()
        await repository.close()


if __name__ == "__main__":
    asyncio.run(main())
