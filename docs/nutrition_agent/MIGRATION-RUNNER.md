# Nutrition Agent Migration Runner

Status: Canonical Phase 0 migration contract for implementation.

This document defines the authoritative one-shot migration runner and validation-only service startup behavior for Nutrition Agent schema changes. It is also the narrowly scoped shared-schema prerequisite for removing Recovery Agent runtime DDL; it does not authorize Recovery feature, route, configuration, deployment, or test changes.

## Command and ownership

Canonical command:

```powershell
uv run python -m app.db.migrate
```

The module is `C:\dev\multi-agent-coach\app\db\migrate.py`. It exposes `async def run_migrations(*, check_only: bool = False) -> MigrationValidationResult`, `async def validate_compatible_schema() -> MigrationValidationResult`, and `main() -> None`; `python -m app.db.migrate --check` calls validation only and makes no schema or ledger mutation. `MigrationValidationResult` contains only `compatible: bool`, `checks: dict[str, Literal["ok", "failed"]]`, and an internal-only reason. Main API, Nutrition Agent, and Recovery Agent call `validate_compatible_schema()` after opening their pool; their readiness route maps its public output to check names only.

The main API, Recovery Agent, and Nutrition Agent must not create, alter, or drop application tables at normal startup. `app.db.database:init_db()` becomes connection plus compatibility validation and may not call `setup_database()`, `run_migrations()`, or seeding. `NutritionRepository.connect()` and `RecoveryRepository.connect()` must stop calling `ensure_schema()`; those methods are removed or reduced to read-only compatibility checks. Services perform connection and compatibility validation only, and readiness returns `503` until the ledger/schema is compatible.

Database creation/provisioning is infrastructure-owned. Admin seeding is a separate one-shot job after migration and must not invoke legacy startup migrations.

## Bootstrap and ledger table

Database and role creation/provisioning are infrastructure-owned and are never performed by this CLI. On a clean, provisioned database only, before any ledger access, the runner may execute exactly `CREATE SCHEMA IF NOT EXISTS systemdb`. This narrowly permits historical migration `000` to run from an empty schema without a bootstrap ordering failure. It may then create `systemdb.schema_migrations` if absent. No service process may use this exception.

Outside that clean-install bootstrap statement and creation of the ledger itself, the runner may execute schema-mutating DDL only by applying a discovered migration file in its transaction. It must not create, alter, or drop application objects outside migrations.

Required columns:

- `version` text primary key, e.g. `000`, `006`.
- `filename` text not null.
- `sha256` char(64) not null, computed from raw migration file bytes.
- `applied_at` timestamptz not null default `now()`.

Ledger writes occur in the same transaction as the corresponding migration. The runner records timing in structured job logs/metrics, not the ledger. Historical checksum validation happens before any forward ledger mutation.

## Locking

The runner takes one session-scoped PostgreSQL advisory lock for the complete run. The lock serializes concurrent runners while allowing each migration and ledger insert to remain independently atomic. If the lock cannot be acquired within the configured timeout, fail before mutation.

## Legacy baseline

Historical migrations `000` through `005` are immutable compatibility facts. On an existing database without ledger rows, the runner validates `app/db/migrations/legacy_000_005_manifest.json` instead of rerunning historical SQL. Required validation includes raw-file checksums, required `systemdb` objects/columns/indexes/constraints, and `food_cache` historical content fingerprint. Migration `003` recovery objects are checked only as shared-order compatibility facts.

If validation passes, insert baseline ledger rows for `000`-`005` as `applied`, then apply `006+`. If validation fails, stop before mutation and report required operator action.

## Clean install

On a clean provisioned database, the runner performs the narrowly allowed `systemdb` bootstrap, creates the ledger, then applies `000` through latest exactly once in filename order. Rerunning must be a no-op after checksum/ledger validation.

## Forward migrations

Forward nutrition schema changes start at `006`. Never edit `000`-`005`. Forward migrations must be backward-compatible with disabled Nutrition Agent behavior and must include matching schema-readiness validation. The runner discovers only files matching `^[0-9]{3}_.+\.sql$`, sorted by numeric version, rejects duplicate/gapped new versions, and computes raw-byte SHA-256 before opening a forward-migration transaction.

## Failure behavior

Fatal before mutation: edited historical file, checksum mismatch, missing required legacy object, altered food-cache baseline, invalid schema name, or lock timeout. Fatal during forward migration: transaction rolls back and no successful ledger row is inserted.

## Required tests

- Clean install applies `000`-latest and ledger rows.
- Legacy `000`-`005` database baselines without rerunning SQL, then applies `006+`.
- Rerun is no-op.
- Historical checksum mismatch fails before mutation.
- Missing/altered required objects fail before mutation.
- Concurrent runners serialize on the advisory lock.
- Main API and Nutrition Agent readiness cannot issue DDL.
