# Nutrition Agent Testing

Status: Canonical Phase 0 testing contract for implementation.

## Test locations

- Main API nutrition tests: `c:\\dev\\multi-agent-coach\\tests\\nutrition\\`.
- Main API migration tests: `c:\\dev\\multi-agent-coach\\tests\\test_migration_runner.py` or `tests\\db\\`.
- Nutrition Agent tests: `c:\\dev\\multi-agent-coach\\services\\nutrition_agent\\tests\\`.

Both repository roots contain an `app` package. Service tests must be executed with the service directory as the working directory so imports resolve to `services/nutrition_agent/app`, never the main API package. Main-API tests run from repository root. Do not run both suites in one pytest process or depend on ambient `PYTHONPATH` ordering.

## Baseline commands

Current baseline:

```powershell
uv run pytest -q
```

Required commands as features land:

```powershell
uv run python -m app.db.migrate --check
uv run pytest tests/nutrition -q
# PostgreSQL-backed food-cache integration test (requires the isolated URL below).
$env:NUTRITION_TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/nutrition_test"
uv run pytest tests/nutrition/test_food_cache_postgres_integration.py -q
# Opt-in live smoke: reads local USDA_FDC_API_KEY and never prints it/payloads.
$env:NUTRITION_RUN_LIVE_USDA_TESTS = "1"
uv run pytest tests/nutrition/test_usda_live_smoke.py -q
Push-Location services/nutrition_agent; python -m pytest tests -q; Pop-Location
uv run gitleaks detect --source . --redact --verbose
```

## Compose readiness smoke

Run this from `c:\\dev\\multi-agent-coach\\` with Docker running. The opt-in
script uses an isolated Compose project, waits for the one-shot migration job
and runtime health checks, verifies public liveness/readiness, verifies that
Nutrition Agent is published only to loopback, and removes its resources:

```powershell
.\scripts\test-compose-deployment.ps1
```

Compose explicitly enables the Nutrition Agent client with the in-network URL
`http://nutrition-agent:8003`; its rollout remains controlled by
`NUTRITION_AGENT_ROLLOUT_PERCENT` and defaults to `0`.

## PostgreSQL fixture contract

Repository and migration tests use isolated database `nutrition_test` with schema `systemdb`. Tests must fail closed if the URL database name is not `nutrition_test`, if it equals `DATABASE_URL`, or if the target appears non-disposable. CI uses PostgreSQL 16.

`NUTRITION_TEST_DATABASE_URL` is mandatory for PostgreSQL-backed tests. The
fixture validates it before opening a connection, temporarily supplies that
same approved URL to the migration runner, applies the ledger, and cleans up
only its reserved test food-cache IDs. Database provisioning remains
infrastructure-owned; the test suite never creates `nutrition_test`.

## Required automated coverage

- Deterministic safety: structured enums, trigger-code order, escalation blocks, disclaimer preservation, and privacy-safe persistence.
- Targets/plans: TDEE, macro targets, calorie floors, non-mutating calculation, explicit save, versioning, and safety refusal.
- Food search: cache hit, cache miss with normalized USDA upsert, no-key/cache-only, timeout/quota/network failure, stale cache, malformed upstream payload, and suppression cache.
- Live USDA smoke is opt-in only (`NUTRITION_RUN_LIVE_USDA_TESTS=1`) and requires a local `USDA_FDC_API_KEY`; it asserts normalized records without logging keys or upstream payloads.
- Migration runner: clean install, legacy baseline, checksum mismatch, missing object, food-cache fingerprint mismatch, no-op rerun, and concurrent lock serialization.
- Public routes: JWT required, no public `user_id`, ownership isolation, validation envelope, pagination/date/timezone bounds, rate limits, and dependency failures.
- Internal routes/client: `NUTRITION_INTERNAL_SERVICE_TOKEN`, request shaping, timeout, 5xx, stable errors, and no mutation fallback.
- Import isolation: a sentinel main-API test and service test each assert their imported `app.__file__` belongs to their respective root; CI invokes their commands in separate processes.
- Orchestrator rollout: disabled service, rollout `0`, `10`, `50`, `100`, stable SHA-256 buckets, invalid config readiness failure, timeout/5xx local fallback.
- Observability: request-ID propagation, redacted logs, low-cardinality labels, no sensitive values in metrics/traces/logs.

## Manual/release evidence

Before user-facing enablement, record: passing full test suite, migration check, secret scan, Compose smoke, readiness smoke, USDA no-key/outage smoke with mocked upstream, and rollout/rollback dry run.
