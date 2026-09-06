# Nutrition Service: Validated Completed Work Guide

**Status:** Development-core status record — not a production or user-facing-release approval.

**Evidence reviewed:** 2026-09-06. This guide records only work supported by the current implementation and documented focused validation. It does **not** change the authoritative checklist in [the implementation plan](NUTRITION-SERVICE-IMPLEMENTATION-PLAN.md). A capability is not complete merely because its code exists: it requires the acceptance evidence required by that plan.

## Scope and status rules

The Nutrition service consists of an authenticated main-API boundary at `/api/nutrition`, a private token-authenticated Nutrition Agent boundary at `/v1/nutrition`, and the main chat/orchestrator integration. The service must remain private; it is never a browser/public-ingress API.

- **Validated completed work** means implementation behavior has focused automated-test evidence or explicitly recorded local validation.
- **Implemented, pending validation** means code and contracts exist, but a required validation scenario has not been executed or confirmed.
- **Core gap** means a non-deferred development-core requirement remains incomplete; it prevents an implementation-complete claim.
- **Deferred work** is intentionally outside the 2026-08-31 development-core pass. It remains mandatory before user-facing enablement and must not be described as complete.

Authoritative contracts are [API-CONTRACT.md](API-CONTRACT.md), [SAFETY-POLICY.md](SAFETY-POLICY.md), [MIGRATION-RUNNER.md](MIGRATION-RUNNER.md), [OPERATIONS.md](OPERATIONS.md), and [TESTING.md](TESTING.md).

## Validated completed work

| Area | Current validated evidence | Traceability |
| --- | --- | --- |
| Contract and boundary foundations | Canonical public/private path, ownership, validation-envelope, safety-projection, target-versioning, and fallback contracts are documented. Public handlers derive the user identity from JWT rather than accepting `user_id`; private user paths require the internal token. | Plan Pack A; API contract global conventions and error contract. |
| Migration-ledger acceptance | A ledger-backed migration runner, legacy manifest, forward migrations `006`–`009`, and validation-only schema interfaces are present. Core-1 acceptance on an isolated `nutrition_test` database verified clean install and no-op rerun, legacy `000`–`005` baseline upgrade through `009`, checksum-mismatch failure before ledger creation, concurrent-runner safety, and read-only compatibility validation. | Plan Pack B; migration-runner contract; 2026-09-06 plan log; `tests/nutrition/test_repository_foundations.py`; `tests/nutrition/test_food_cache_postgres_integration.py`. |
| Persistence and owned programmatic operations | The codebase contains profile, meal-log CRUD/list filtering, target calculate/save/current lookup, daily history/adherence, assessment history, meal-plan, and shared food-reference operations through the private client and authenticated public routes. Focused main-API Nutrition validation recorded **188 passed, 1 skipped** on 2026-09-03. | Plan development-core decision (Section 14); API contract operation definitions; 2026-09-03 plan log. |
| Deterministic safety and privacy projection | `nutrition-safety-v1` supplies typed, ordered safety findings; deterministic escalation and referral behavior; calorie-floor and BMI handling; and sanitized assessment-history projections. The policy prohibits persistence/logging of raw disclosures, request context, prompts, reasoning, and tool traces. | Plan Pack A and Phase 6 safety requirements; Safety Policy. |
| Food-reference resilience foundation | Cache-first normalized search uses a 30-day freshness window and serves stale cache only through 180 days. No-result and unavailable normalized queries persist a 15-minute suppression; FDC-ID refresh suppression uses the same period. Validated USDA bounds/timeouts and an in-memory per-instance limiter apply 30/minute, 1,000/hour, and 10,000/day across search and detail HTTP calls. Deterministic tests cover no-key, upsert, outage/stale fallback, expiry, no-result suppression, circuit behavior, and quota; PostgreSQL integration applies migration 009 and verifies persisted query suppression. | Plan cache-first requirement; `app/db/migrations/009_nutrition_food_search_suppressions.sql`; `tests/nutrition/test_food_reference.py`; `tests/nutrition/test_food_cache_postgres_integration.py`. |
| Private-client resilience | The client owns a pooled async HTTP client, uses canonical timeouts, retries qualifying idempotent reads once with jitter, does not retry mutations, and has a five-failure/30-second circuit with one half-open probe. Recorded validation: focused Nutrition suite **156 passed, 1 skipped**, Ruff, compilation, and `git diff --check` (2026-09-01). | API contract resilience section; 2026-09-01 plan log. |
| Public request hardening | Strict public request models, model-dumped forwarding, request-ID-preserving validation envelopes, and safe downstream error mapping have recorded focused validation: **14 passed**, then Nutrition suite **159 passed, 1 skipped**, compilation, diff check, and Ruff (2026-09-01). | API contract public errors; 2026-09-01 plan log. |
| Chat safe fallback baseline | Chat skips the remote Nutrition service when graph state lacks a valid positive user ID, honors rollout bucketing, preserves returned escalation metadata, and falls back to the local specialist on service failure. Focused coverage proves valid-ID dispatch and missing-ID fallback. | Plan orchestrator fallback contract; `tests/nutrition/test_chat_nutrition_service.py`; Operations resilience/fallback section. |

## Reproducing the currently recorded validation

Run main-API tests from the repository root. Run Nutrition Agent tests in a **separate process** with its own working directory because both roots have an `app` package.

```powershell
Set-Location C:\dev\multi-agent-coach
uv run pytest tests/nutrition -q

Push-Location C:\dev\multi-agent-coach\services\nutrition_agent
python -m pytest tests -q
Pop-Location
```

Expected result: focused unit/client/route/service tests pass; the PostgreSQL food-cache integration case may be skipped when `NUTRITION_TEST_DATABASE_URL` is not configured. A skipped database integration test is not migration or database acceptance evidence.

For static hygiene after a code change, use the repository’s configured tools:

```powershell
Set-Location C:\dev\multi-agent-coach
uv run ruff check app services/nutrition_agent tests/nutrition
git diff --check
```

Do not combine the main-API and Nutrition Agent pytest suites in one pytest process or rely on ambient `PYTHONPATH` ordering.

## Migration validation procedure — required but not yet evidenced

The 2026-09-03 `--check` run correctly reported unapplied migrations against the configured local database. No mutation was performed because that target was not independently established as disposable. Do **not** run the apply command against a shared, developer, staging, or production database merely to make this guide green.

Provisioning the database is infrastructure-owned. After an explicitly disposable PostgreSQL database is provisioned, set the connection variables and run the following scenarios, recording command output and ledger rows for each:

1. **Clean install:** run `uv run python -m app.db.migrate`; verify `000` through `008` ledger entries, required schema objects, then verify a rerun is a no-op.
2. **Legacy baseline/upgrade:** prepare only the immutable `000`–`005` historical schema/content with no ledger; run the migration command; verify baseline rows are inserted without replaying historical SQL and `006`–`008` are applied.
3. **Historical checksum failure:** alter only a disposable copy of a historical migration or manifest input; run the command; verify failure occurs before ledger/schema mutation. Restore the exact tracked artifact afterward.
4. **Concurrent runner serialization:** start two runners against the same disposable database; verify the advisory lock serializes them and leaves one correct ledger sequence.
5. **Readiness/no-runtime-DDL:** start each service only after the migration job, probe `/health/ready`, and verify incompatible schemas return `503` without application DDL.

For PostgreSQL-backed tests, use only the isolated database name required by the testing contract:

```powershell
$env:NUTRITION_TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/nutrition_test"
uv run pytest tests/nutrition/test_food_cache_postgres_integration.py -q
```

The fixture must fail closed unless the URL points to disposable `nutrition_test` and is different from `DATABASE_URL`.

## Remaining non-deferred development-core gaps

These gaps must be resolved and validated, or receive an explicit accepted deferral in the implementation plan, before describing development-core implementation as complete.

| ID | Gap | Why it remains open | Required completion evidence |
| --- | --- | --- | --- |
| Core-1 | Migration-runner validation | Completed 2026-09-06 against the explicitly isolated local `nutrition_test` database: clean install and no-op rerun produced the complete `000`–`009` ledger; a legacy `000`–`005` schema was baselined without replay and upgraded through `009`; an intentionally mismatched historical manifest failed before creating `systemdb`; concurrent runners completed with an unchanged complete ledger; and read-only compatibility validation passed. | Acceptance script output recorded 2026-09-06; PostgreSQL food-cache integration: **1 passed in 0.63s**. |
| Core-2 | Cache/USDA policy verification | Completed 2026-09-06: recorded opt-in live USDA smoke (`uv run pytest tests/nutrition/test_usda_live_smoke.py -q`: **1 passed in 2.05s**) in addition to existing cache/resilience coverage. | Keep live smoke opt-in and retain no-key/no-payload logging safeguards. |
| Core-3 | Safety threshold consistency audit | Completed 2026-09-06: aligned legacy macro targets so `other` uses the canonical 1200 kcal/day floor; assessment already used that floor. Added exact floor, BMI, and weekly-loss boundary regression coverage. | Focused safety/chat/client validation: **141 passed**. |
| Core-4 | Complete validated profile in chat orchestration | Completed 2026-09-06: chat performs an ownership-scoped private profile read, allowlists and validates it as `NutritionProfileUpsert`, then supplies it only to private evaluation. Missing/invalid profile and profile/evaluation dependency failures preserve local-specialist fallback. | Focused safety/chat/client validation: **141 passed**; the transient profile is not persisted in assessment history. |

## Explicitly deferred work — not completed or accepted as release evidence

The 2026-08-31 Section 14 decision defers new or expanded automated tests/fixtures, CI, secret scanning, Redis/rate-limit infrastructure, Compose/deployment work, pre-production/staging, credential governance, observability rollout, load testing, and rollout/rollback execution. The following remain required before user-facing enablement:

- Redis-backed public and internal rate limits, USDA quota controls, and optional LLM cost/user quotas.
- Broader automated coverage: database/migration, route ownership, resilience, safety matrix, concurrency, integration, load/performance, observability, and import isolation as specified in `TESTING.md`.
- Credential-owner attestation, secret scanning, and production credential/USDA governance.
- CI, disposable test-database fixture ownership, deployment/Compose image validation, pre-production readiness, and release rollout/rollback drills.
- Observability rollout, redacted metrics/traces/log evidence, retention/deletion operational proof, and current API/deployment documentation validation.
- User-facing-release gates in implementation-plan Definition of Done, including migration upgrade evidence and complete safety-policy validation.

## Operational safety reminders

- Keep `USDA_FDC_API_KEY` absent for cache-only local behavior unless an approved environment supplies it. Never commit API keys or internal tokens.
- Live USDA smoke is opt-in through `NUTRITION_RUN_LIVE_USDA_TESTS=1`. Recorded local evidence: `uv run pytest tests/nutrition/test_usda_live_smoke.py -q` ? **1 passed in 2.05s** (2026-09-06). It must never print the key, URL, or upstream payload.
- Normal service startup must validate database/schema compatibility only. The one-shot migration job is the schema mutator; runtime services must not migrate, seed, or execute DDL.
- `/health/live` is dependency-free. `/health/ready` must return `503` until configuration, database connectivity, and schema compatibility pass.
- Chat alone may fall back to the local nutrition specialist. Programmatic Nutrition routes return documented dependency/service-disabled errors and must not mutate locally on a private-service failure.
- Keep Nutrition Agent private: only the main API may call `/v1/nutrition/*` with `X-Internal-Service-Token` over private networking.

## Completion update checklist

When evidence is obtained, update the authoritative plan and this guide together:

1. Link the exact command, environment classification, date, and pass/fail/skip count.
2. Mark only the validated child item complete; retain unexecuted siblings as open or deferred.
3. Record any threshold or contract decision in the plan’s Section 14 before changing a canonical policy.
4. Re-run the relevant main-API and service tests in separate processes.
5. Recheck `git diff --check` and confirm no credential, raw safety context, or sensitive payload was introduced into tracked files or test output.

Until all Core-1 through Core-4 items are resolved or explicitly deferred and the separate release register is completed, this document must be read as a development-core progress guide, not a release approval.