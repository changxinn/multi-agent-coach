"""One-shot, ledger-backed PostgreSQL migration runner.

Application processes only use :func:`validate_compatible_schema`; schema
mutation is reserved for ``python -m app.db.migrate``.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
MANIFEST_PATH = MIGRATIONS_DIR / "legacy_000_005_manifest.json"
MIGRATION_PATTERN = re.compile(r"^(?P<version>[0-9]{3,})_.+\.sql$")
LEGACY_VERSIONS = tuple(f"{number:03d}" for number in range(6))
ADVISORY_LOCK_KEY = 7_246_908_136


@dataclass(frozen=True)
class MigrationValidationResult:
    """Internal compatibility result safe to map to readiness check names."""

    compatible: bool
    checks: dict[str, Literal["ok", "failed"]]
    reason: str | None = None


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    sha256: str


def _database_url() -> str:
    """Return a driver URL suitable for SQLAlchemy's async engine."""
    url = get_settings().DATABASE_URL
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


def test_database_url() -> str:
    """Return the explicitly isolated integration-test URL or fail before I/O."""
    import os

    test_url = os.environ.get("NUTRITION_TEST_DATABASE_URL")
    if not test_url:
        raise RuntimeError(
            "NUTRITION_TEST_DATABASE_URL must be configured for database tests"
        )
    configured_url = os.environ.get("DATABASE_URL")
    if configured_url and test_url == configured_url:
        raise RuntimeError("NUTRITION_TEST_DATABASE_URL must not equal DATABASE_URL")
    if make_url(test_url).database != "nutrition_test":
        raise RuntimeError(
            "NUTRITION_TEST_DATABASE_URL must target database nutrition_test"
        )
    return test_url


def _discover_migrations() -> list[Migration]:
    migrations: list[Migration] = []
    versions: set[str] = set()
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = MIGRATION_PATTERN.fullmatch(path.name)
        if not match:
            raise RuntimeError(f"Invalid migration filename: {path.name}")
        version = match.group("version")
        if version in versions:
            raise RuntimeError(f"Duplicate migration version: {version}")
        versions.add(version)
        migrations.append(
            Migration(version, path, hashlib.sha256(path.read_bytes()).hexdigest())
        )

    if not migrations:
        raise RuntimeError(f"No migrations found in {MIGRATIONS_DIR}")
    ordered = sorted(migrations, key=lambda migration: int(migration.version))
    forward = [
        int(migration.version) for migration in ordered if int(migration.version) >= 6
    ]
    if forward and forward != list(range(6, forward[-1] + 1)):
        raise RuntimeError(
            "Forward migration versions must start at 006 and be contiguous"
        )
    return ordered


def _legacy_manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _validate_legacy_file_checksums(migrations: list[Migration]) -> None:
    actual = {migration.version: migration for migration in migrations}
    manifest = _legacy_manifest()
    for entry in manifest["legacy_migrations"]:  # type: ignore[index]
        version = entry["version"]  # type: ignore[index]
        migration = actual.get(version)
        if migration is None or migration.path.name != entry["filename"]:  # type: ignore[index]
            raise RuntimeError(f"Historical migration {version} is missing or renamed")
        if migration.sha256 != entry["sha256"]:  # type: ignore[index]
            raise RuntimeError(
                f"Historical migration checksum mismatch: {migration.path.name}"
            )


async def _table_exists(connection: AsyncConnection, table: str) -> bool:
    result = await connection.execute(
        text("SELECT to_regclass(:table_name) IS NOT NULL"),
        {"table_name": f"systemdb.{table}"},
    )
    return bool(result.scalar_one())


async def _validate_legacy_schema(connection: AsyncConnection) -> None:
    """Validate baseline objects before recording immutable historical entries."""
    manifest = _legacy_manifest()
    for table, specification in manifest["required_tables"].items():  # type: ignore[index]
        if not await _table_exists(connection, table):
            raise RuntimeError(
                f"Legacy schema is missing required table systemdb.{table}"
            )
        expected_columns = {column["name"] for column in specification["columns"]}
        result = await connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'systemdb' AND table_name = :table_name"
            ),
            {"table_name": table},
        )
        missing = expected_columns - set(result.scalars())
        if missing:
            raise RuntimeError(
                f"Legacy table systemdb.{table} is missing columns: {sorted(missing)}"
            )

    fingerprint = manifest["food_cache"]  # type: ignore[index]
    result = await connection.execute(text("SELECT count(*) FROM systemdb.food_cache"))
    if result.scalar_one() != fingerprint["row_count"]:  # type: ignore[index]
        raise RuntimeError(
            "Legacy food_cache row count does not match the committed baseline"
        )


async def _ensure_ledger(connection: AsyncConnection) -> None:
    await connection.execute(text("CREATE SCHEMA IF NOT EXISTS systemdb"))
    await connection.execute(
        text(
            "CREATE TABLE IF NOT EXISTS systemdb.schema_migrations ("
            "version text PRIMARY KEY CHECK (version ~ '^[0-9]{3,}$'), "
            "filename text UNIQUE NOT NULL, "
            "sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'), "
            "applied_at timestamptz NOT NULL DEFAULT now()"
            ")"
        )
    )


async def _ledger_rows(connection: AsyncConnection) -> dict[str, tuple[str, str]]:
    result = await connection.execute(
        text("SELECT version, filename, sha256 FROM systemdb.schema_migrations")
    )
    return {row.version: (row.filename, row.sha256) for row in result}


def _validate_ledger(
    migrations: list[Migration], rows: dict[str, tuple[str, str]]
) -> None:
    known = {migration.version: migration for migration in migrations}
    unknown = set(rows) - set(known)
    if unknown:
        raise RuntimeError(
            f"Ledger contains unknown migration versions: {sorted(unknown)}"
        )
    for version, (filename, checksum) in rows.items():
        migration = known[version]
        if filename != migration.path.name or checksum != migration.sha256:
            raise RuntimeError(f"Ledger checksum mismatch for migration {version}")


def _migration_statements(script: str) -> list[str]:
    """Split migration SQL on unquoted semicolons for asyncpg prepared statements."""
    statements: list[str] = []
    start = 0
    quote: str | None = None
    in_line_comment = False
    for index, character in enumerate(script):
        previous = script[index - 1] if index else ""
        following = script[index + 1] if index + 1 < len(script) else ""
        if in_line_comment:
            if character == "\n":
                in_line_comment = False
            continue
        if quote:
            if character == quote and previous != "\\":
                quote = None
        elif character == "-" and following == "-":
            in_line_comment = True
        elif character in {"'", '"'}:
            quote = character
        elif character == ";":
            if statement := script[start:index].strip():
                statements.append(statement)
            start = index + 1
    if quote:
        raise RuntimeError("Migration contains an unterminated SQL quote")
    if statement := script[start:].strip():
        statements.append(statement)
    return statements


async def _apply_migration(connection: AsyncConnection, migration: Migration) -> None:
    async with connection.begin():
        for statement in _migration_statements(migration.path.read_text(encoding="utf-8")):
            await connection.execute(text(statement))
        await connection.execute(
            text(
                "INSERT INTO systemdb.schema_migrations (version, filename, sha256) "
                "VALUES (:version, :filename, :sha256)"
            ),
            {
                "version": migration.version,
                "filename": migration.path.name,
                "sha256": migration.sha256,
            },
        )


async def run_migrations(*, check_only: bool = False) -> MigrationValidationResult:
    """Validate or apply migrations under one session-scoped advisory lock."""
    migrations = _discover_migrations()
    _validate_legacy_file_checksums(migrations)
    engine = create_async_engine(_database_url(), pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            if check_only:
                return await _validate_connection(connection, migrations)

            await connection.execute(
                text("SELECT pg_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
            )
            try:
                await connection.commit()
                async with connection.begin():
                    await _ensure_ledger(connection)
                rows = await _ledger_rows(connection)
                _validate_ledger(migrations, rows)
                # Ledger reads implicitly start a SQLAlchemy transaction. End it
                # before opening the independently atomic legacy-baseline write.
                await connection.commit()
                # A nonempty pre-ledger schema is legacy and must never be replayed.
                if not rows and await _table_exists(connection, "users"):
                    await _validate_legacy_schema(connection)
                    legacy = [
                        migration
                        for migration in migrations
                        if migration.version in LEGACY_VERSIONS
                    ]
                    # Legacy validation is read-only, but it likewise starts an
                    # implicit transaction before the atomic ledger baseline.
                    await connection.commit()
                    async with connection.begin():
                        for migration in legacy:
                            await connection.execute(
                                text(
                                    "INSERT INTO systemdb.schema_migrations (version, filename, sha256) VALUES (:version, :filename, :sha256)"
                                ),
                                {
                                    "version": migration.version,
                                    "filename": migration.path.name,
                                    "sha256": migration.sha256,
                                },
                            )
                    rows = await _ledger_rows(connection)
                await connection.commit()
                for migration in migrations:
                    if migration.version not in rows:
                        await _apply_migration(connection, migration)
                return await _validate_connection(connection, migrations)
            finally:
                await connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY}
                )
    finally:
        await engine.dispose()


async def _validate_connection(
    connection: AsyncConnection, migrations: list[Migration] | None = None
) -> MigrationValidationResult:
    checks: dict[str, Literal["ok", "failed"]] = {
        "database": "ok",
        "migration_ledger": "failed",
        "schema": "failed",
    }
    try:
        migrations = migrations or _discover_migrations()
        _validate_legacy_file_checksums(migrations)
        if not await _table_exists(connection, "schema_migrations"):
            return MigrationValidationResult(
                False, checks, "Migration ledger is absent"
            )
        rows = await _ledger_rows(connection)
        _validate_ledger(migrations, rows)
        if set(rows) != {migration.version for migration in migrations}:
            return MigrationValidationResult(
                False, checks, "Not all migrations are applied"
            )
        checks["migration_ledger"] = "ok"
        # Every migration has an observable application object. This remains
        # read-only so service startup and readiness never own schema mutation.
        required_tables = (
            "users",
            "sleep_logs",
            "recovery_checkins",
            "recovery_assessments",
            "nutrition_profiles",
            "meal_logs",
            "nutrition_assessments",
            "food_cache",
            "food_search_suppressions",
            "nutrition_targets",
        )
        missing_tables = [
            table for table in required_tables if not await _table_exists(connection, table)
        ]
        if missing_tables:
            return MigrationValidationResult(
                False,
                checks,
                f"Required application tables are absent: {', '.join(missing_tables)}",
            )
        checks["schema"] = "ok"
        return MigrationValidationResult(True, checks)
    except Exception as error:
        logger.warning("Database compatibility validation failed: %s", error)
        return MigrationValidationResult(False, checks, str(error))


async def validate_compatible_schema() -> MigrationValidationResult:
    """Perform read-only schema and migration-ledger compatibility validation."""
    engine = create_async_engine(_database_url(), pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            return await _validate_connection(connection)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or validate database migrations")
    parser.add_argument(
        "--check", action="store_true", help="Validate only; do not mutate the database"
    )
    arguments = parser.parse_args()
    result = asyncio.run(run_migrations(check_only=arguments.check))
    if not result.compatible:
        raise SystemExit(result.reason or "Database schema is incompatible")
    logger.info("Database migration validation completed: %s", result.checks)


if __name__ == "__main__":
    main()
