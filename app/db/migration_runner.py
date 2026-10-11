"""Versioned PostgreSQL migration execution for controlled deployment tasks."""

from __future__ import annotations

import hashlib
from pathlib import Path


def split_sql_statements(content: str) -> list[str]:
    """Split SQL on semicolons outside single quoted literals."""
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
    trailing = "".join(statement).strip()
    if trailing:
        statements.append(trailing)
    return statements


def executable_sql(content: str) -> str:
    """Remove full-line SQL comments before parsing statement delimiters."""
    return "\n".join(
        line for line in content.splitlines() if not line.strip().startswith("--")
    )


async def run_versioned_migrations(engine, migration_dir: Path, lock_name: str) -> None:
    """Apply each migration exactly once under an advisory transaction lock."""
    migration_files = sorted(migration_dir.glob("*.sql"))
    if not migration_files:
        raise RuntimeError(f"No migration files found in {migration_dir}")

    async with engine.begin() as connection:
        await connection.exec_driver_sql(
            "SELECT pg_advisory_xact_lock(hashtext($1))", (lock_name,)
        )
        await connection.exec_driver_sql(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                checksum VARCHAR(64) NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        for migration_file in migration_files:
            content = migration_file.read_text(encoding="utf-8-sig")
            checksum = hashlib.sha256(content.encode()).hexdigest()
            applied = await connection.exec_driver_sql(
                "SELECT checksum FROM schema_migrations WHERE version = $1",
                (migration_file.name,),
            )
            existing_checksum = applied.scalar_one_or_none()
            if existing_checksum:
                if existing_checksum != checksum:
                    raise RuntimeError(
                        f"Migration checksum changed: {migration_file.name}"
                    )
                continue
            for statement in split_sql_statements(executable_sql(content)):
                if statement:
                    await connection.exec_driver_sql(statement)
            await connection.exec_driver_sql(
                "INSERT INTO schema_migrations (version, checksum) VALUES ($1, $2)",
                (migration_file.name, checksum),
            )
