# Nutrition Service Implementation Plan

**Status:** Active, resumable implementation plan
**Last reviewed:** 2026-08-31
**Implementation readiness:** A development-core implementation pass is authorized as of 2026-08-31. The current working-tree scaffold remains replaceable and must conform to the canonical API, safety, privacy, and migration contracts before it is retained. New automated-test work, CI/fixture work, and all pre-production/production processes are deferred for this pass. Full user-facing enablement remains gated by product/privacy/safety approval, USDA credential-governance evidence, migration-ledger validation, safety-policy validation, tests, documentation, and release gates.
**Scope:** Complete the Nutrition Agent and its direct main-API/database integration as a secure, user-facing nutrition-management capability while retaining its private microservice boundary and deterministic safety controls. This plan excludes Recovery Agent features, routes, configuration, deployment, and tests, but includes the minimal shared-schema prerequisite of removing Recovery runtime DDL in favor of migration-ledger compatibility validation. Immutable historical migration `003` remains a read-only shared-database compatibility fact only.

---

## How to Resume This Plan

This document is the source of truth for implementation progress. Update it in the same change set as completed work.

### Status markers

- `[ ]` Not started.
- `[~]` In progress. Add a dated note explaining the current state, decision, or blocker.
- `[x]` Complete **and validated** against the item's stated acceptance criteria.
- `[-]` Intentionally deferred or not applicable. State why and link the replacement decision/work item.

### Continuation protocol

1. During the active 2026-08-31 development-core pass, follow the **Development-core execution order** below. Skip every item explicitly deferred by Section 14 even if it is the first unchecked Master Checklist item; leave deferred work uncompleted and do not change it to `[x]`. Outside that pass, find the first required `[ ]` or `[~]` item in the **Master Checklist**.
2. Read its target file(s), named function(s), dependencies, and validation command before changing code.
3. Change the item to `[~]` when work begins.
4. Change a development-core item to `[x]` only after implementation review and the applicable non-destructive local validation have passed. Change a deferred test, CI, deployment, rollout, or production item to `[x]` only after its stated validation evidence has passed in its later dedicated pass.
5. Record material decisions or blockers directly beneath the affected item, using a dated note.
6. Do not mark a phase or release complete until all required child items for that phase or release are `[x]`; development-core implementation does not complete a phase containing deferred release evidence.

> **Current resume point:** Begin the development-core vertical slice with canonical typed schemas and the deterministic safety/privacy projection foundation, then implement repository operations, private routes, main-API routes/client, and orchestrator/chat integration in the binding order below. The previously inventoried Nutrition scaffold remains a rewrite candidate, not an approved compatibility surface. Tests, CI/fixtures, pre-production, and production/release work are explicitly deferred by the 2026-08-31 Section 14 decision and must not be marked complete in this pass. The primary user-facing path for the eventual release remains the authenticated orchestrator/chat endpoint; dedicated `/api/nutrition/*` routes are backend programmatic capabilities for admin/internal workflows and future UI readiness unless a later decision makes them primary user-facing routes.

### Development-first implementation mode

For the current implementation pass, the authorized deliverable is development-core functionality: local/dev Nutrition Agent behavior, private routes, public programmatic routes, persistence, deterministic safety logic, privacy-safe projections, and chat integration. Automated-test implementation, CI and isolated-fixture work, and all pre-production/production release gates are intentionally deferred. This pass may use non-destructive local validation (for example syntax, imports, linting, OpenAPI inspection, and service/readiness checks where dependencies exist), but it does not claim test or release readiness. Production enablement remains blocked until governance approvals, credential attestation, production secret management, Redis enforcement, CI/staging evidence, automated tests, load testing, and rollout evidence are completed.

**Required before development-core implementation:** the canonical API, safety, migration, and operations contracts; a documented disposition for legacy scaffolding; cache-only/no-key behavior; privacy-safe persistence boundaries; migration-ledger ownership; and validation-only service startup. **Explicitly deferred in this pass:** new test suites, isolated test-database fixtures, CI wiring/evidence, secret scanning, deployment/Compose work, pre-production/staging, production credential governance, Redis/rate-limit infrastructure, observability rollout, load testing, and rollout/rollback execution. **Required only before production/user-facing enablement:** product/privacy/safety approval, USDA credential rotation/attestation, production secret-manager and Redis enforcement, CI/staging/load evidence, complete automated tests, and rollout approval. Deferred evidence must not block implementation of the local deterministic path.

### Development-core execution order

The next implementation run must perform only the following local/dev core work, in this order, and must not begin deferred operational or release work:

1. Implement canonical typed schemas, deterministic `nutrition-safety-v1` assessment, disclaimer enforcement, and user-safe/redacted assessment projections.
2. Implement the migration ledger, forward nutrition migration(s), schema-compatibility validation, and validation-only application startup; do not add Compose jobs, CI fixtures, or deployment wiring.
3. Implement ownership-scoped repository operations for profiles, meal logs, targets, history, assessments, and normalized food cache data.
4. Implement canonical private Nutrition Agent routes, including deterministic calculations, versioned target saves, daily history/adherence, restriction-safe meal planning, assessment history, and cache-first food lookup with development cache-only/no-key behavior.
5. Implement authenticated main-API schemas and `/api/nutrition/*` programmatic routes, deriving ownership solely from JWT-backed `current_user`, plus matching pooled async client methods and safe error mapping.
6. Integrate the canonical Nutrition evaluation path into the orchestrator/chat flow with deterministic safe fallback behavior.
7. Perform only non-destructive local validation such as syntax/import checks, linting where available, OpenAPI inspection, and service/readiness checks where dependencies exist. Do not create or expand tests, fixtures, CI, Compose/deployment, rate limiting, observability rollout, load tests, or release/rollout artifacts.

This order supersedes older Phase ordering and “recommended first slice” wording only for the active development-core pass. It does not relax canonical API compatibility, deterministic safety, privacy-safe persistence, JWT-derived ownership, migration-ledger ownership, private service-token enforcement, or validation-only startup.

---

## 1. Goals and Boundaries

### Goals

1. Give authenticated users ownership-safe operations for nutrition profiles, meal logs, food search, targets, plans, history, and assessment history.
2. Preserve the Nutrition Agent as an internal service protected by `X-Internal-Service-Token`.
3. Use deterministic calculations and safety escalation before optional LLM presentation.
4. Make TDEE, macro-target, meal-planning, and cache-first USDA functionality usable rather than dormant utility code.
5. Provide complete test coverage, operational documentation, and a safe rollout path.

### Non-goals for this implementation

- Diagnosing, treating, or replacing professional medical/nutrition care.
- Barcode scanning, wearable synchronization, a recipe marketplace, or a calendar UI.
- Replacing the existing LangGraph routing model.
- Exposing the nutrition microservice directly to browsers or external callers.
- Recovery Agent code, configuration, startup behavior, deployment, tests, or schema-remediation work. The migration ledger may verify immutable historical `003` state, but this does not assign Recovery ownership to this plan.

---

## 1.1 Implementation Decisions (Binding Defaults)

These decisions remove ambiguity for implementation. A later change requires a dated entry in Section 14, a migration/compatibility assessment where data is affected, and updated tests and API documentation.

### Default precedence

Sections 1.1, 6, 9, 12, and 13 are the authoritative implementation defaults. Any later change requires a dated Section 14 decision, a compatibility assessment where data is affected, and matching updates to tests and API documentation.

### Legacy scaffold disposition

- `services/nutrition_agent/app` is an inventory scaffold, not the executable first-release contract. Its existing unscoped private routes, runtime DDL, response `reasoning`/`tool_trace`, broad phrase lists, raw-message LLM context, and serialized assessment persistence are non-compliant with the canonical contracts and must not be extended as a compatibility surface.
- Replace the scaffold private routes and schemas with the canonical paths and projections in `docs/nutrition_agent/API-CONTRACT.md`. Because the private service has no browser/external ingress, no legacy route compatibility period is required. Remove obsolete routes only in the same change set that introduces their canonical replacement.
- Do not enable the current optional LLM path. Reimplement presentation only after the typed safety decision, sanitized persistence projection, and deterministic fallback pass their regression tests.

### Service identity and credentials

- Introduce **Nutrition-only** configuration names: `NUTRITION_INTERNAL_SERVICE_TOKEN` in the main API and Nutrition Agent. Do not change the naming, configuration, or behavior of other agents as part of this work.
- The main API sends this value only in `X-Internal-Service-Token`; the Nutrition Agent validates it on every `/v1/nutrition/*` endpoint. Health liveness remains unauthenticated.
- In deployed environments, the nutrition service has no public ingress and is reachable only from the main API over the private service network. Binding to loopback in local Compose is convenience, not authorization.
- Tokens and third-party keys are secret-manager/environment inputs only. Configuration defaults and documentation may show placeholders but never working credentials.
- Credential remediation covers every tracked file and the repository history. The authorized credential owner must rotate/revoke the exposed USDA key, record whether history rewriting is permitted, and retain the revocation/rotation attestation plus a passing CI secret-scan result before user-facing enablement. Implementation authors must not self-certify this gate.

### Service enablement and rollout assignment

- `USE_NUTRITION_AGENT_SERVICE` is the master enablement switch. When false, all users retain the existing local specialist behavior. When true, `NUTRITION_AGENT_ROLLOUT_PERCENT` is required in deployed environments, is an integer from `0` through `100`, and controls the percentage of authenticated users routed to the Nutrition Agent.
- Assign a user deterministically and stickily by encoding the authenticated numeric `user_id` as its UTF-8 decimal representation, calculating SHA-256, interpreting the first eight digest bytes as an unsigned big-endian integer, and taking modulo 100. The user is enabled when this bucket is less than `NUTRITION_AGENT_ROLLOUT_PERCENT`. Do not use Python's process-randomized `hash()`, random assignment, request IDs, IP addresses, or mutable profile data. `0` routes no users and `100` routes every authenticated user.
- Missing, non-integer, or out-of-range rollout configuration is fatal to main-API readiness when the master switch is enabled. Unit tests must prove stable assignment and the `0`, `10`, `50`, and `100` boundaries.

### Public API conventions

- Public routes are rooted at `/api/nutrition`; internal routes are rooted at `/v1/nutrition`. Only the main API exposes public nutrition operations.
- Public bodies never include `user_id`; handlers derive it from `get_current_user()["id"]`. Internal bodies/path parameters include `user_id` because the main API is the trusted caller.
- Use ISO-8601/RFC 3339 timestamps with offsets. `start_date`/`end_date` are calendar dates interpreted in an explicit user timezone; until user timezone support exists, accept a required `timezone` IANA name on history/list requests and reject invalid names.
- Use offset pagination initially: `limit` defaults to 20 and is capped at 100; `offset` defaults to 0 and is capped at 10,000. Return `{items, limit, offset, total}`. Do not claim cursor support unless it is implemented in a later version.
- Use one stable public error envelope: `{"error": {"code": string, "message": string, "request_id": string}}`. Document status codes and codes per endpoint. Internal error details, stack traces, service tokens, and upstream payloads never reach the browser.
- `GET /profile` returns `404` with `NUTRITION_PROFILE_NOT_FOUND` if no profile exists. `PUT /profile` is a full validated upsert; partial update support is deferred rather than implied.

### Meal logs, privacy, and concurrency

- Implement meal-log create, list, read, update, and delete. Updates use full replacement (`PUT`) and deletes are hard deletes because no audit-retention requirement is approved for this release. The decision must be revisited before regulated/audit requirements are introduced.
- Meal-log creation has no idempotency-key contract during development; each valid create request creates a distinct meal-log record. API-level idempotency is deferred to a pre-production hardening decision. If approved, it requires a versioned API contract, a forward-only migration, replay/conflict semantics, a retention/expiry policy, and concurrent-write integration tests.
- Profile updates are last-write-wins for this release. Return `updated_at`; optimistic concurrency/versioning is explicitly deferred and must be added before clients require conflict detection.
- Retain meal logs and assessments until user deletion or account deletion. A future retention duration, legal hold, export, or audit policy requires a separate approved privacy decision before implementation.

### Targets, history, and adherence

- Target calculation is informational by default. Persist a target only through an explicit `POST /api/nutrition/targets` save action; calculation endpoints never mutate state.
- Persisted targets are immutable versioned records with `effective_from` and optional `effective_to`; one target may be active for a user at a time. A daily history calculation uses the target effective for that local calendar day and returns `null` when no comparable target exists.
- The initial history window is `window_days=7`, constrained to 1–31 days. Aggregate meal logs by local calendar day. Averages use only days containing at least one log with the applicable nutrient value; missing-log calendar days never count as zero.
- Report adherence only when at least 3 logged days in the requested window have an applicable target. For each comparable day, calorie adherence is `min(actual_calories / target_calories, target_calories / actual_calories) * 100`, rounded to one decimal; the response value is the arithmetic mean of comparable daily percentages. Macro adherence is deferred until persisted macro targets and a reviewed formula are implemented. Return `null`, never a fabricated percentage, when evidence is insufficient.

### Safety and presentation

- The Nutrition Agent must not provide diagnosis, treatment, medication/supplement dosing, or prescriptive calorie-deficit/meal-plan guidance for an `escalate` outcome. Escalations return deterministic user-safe referral text only and do not call the LLM.
- A policy version is persisted and returned with every assessment. Any change to thresholds, disclaimer, escalation behavior, or target safety controls updates the policy changelog and regression coverage.
- Safety context is optional, request-scoped input for assessment, target calculation, target save, and meal-plan generation. It is never written to nutrition profiles, meal logs, targets, assessment response JSON, tool traces, logs, or metric labels. Persist only stable trigger codes, policy version, timestamp, and the approved non-sensitive escalation projection in assessment history. A future decision to retain raw medical disclosures requires an approved privacy/retention policy and a forward migration.
- Define `pregnancy_lactation_status` as exactly one of `unknown`, `not_pregnant_or_breastfeeding`, `pregnant`, `breastfeeding`, or `pregnant_and_breastfeeding`; define `medical_conditions` as a deduplicated list of at most six values from `diabetes`, `uses_insulin_or_glucose_lowering_medication`, `kidney_disease`, `heart_disease`, `hypertension`, and `eating_disorder_history`. These are lowercase machine enums; unknown values return `422`, rather than being silently mapped from arbitrary prose. `unknown` is not a negative assertion and never suppresses message-derived safety escalation.
- Positive structured values map deterministically to Section 9.12 codes: any pregnant/breastfeeding value to `PREGNANCY_OR_BREASTFEEDING`; diabetes or glucose-lowering medication to `DIABETES_OR_INSULIN`; kidney disease to `KIDNEY_DISEASE`; heart disease/hypertension to `HEART_DISEASE_OR_HYPERTENSION`; and eating-disorder history to `EATING_DISORDER_HISTORY`. Combine structured and bounded phrase-derived findings into a de-duplicated, policy-defined stable order. Safety escalation always precedes target calculation/save, meal planning, and LLM presentation.

### Health, operational, and test-fixture contract

| Concern | Binding default | Required implementation evidence |
|---|---|---|
| Health endpoints | `GET /health/live` is unauthenticated, performs no database, network, migration, or configuration check, and always returns `200 {"status":"live"}` while the process can serve requests. `GET /health/ready` is unauthenticated and returns `200 {"status":"ready","checks":{"configuration":"ok","database":"ok","schema":"ok"}}` only when required configuration is valid, the database pool can execute `SELECT 1`, and the migration ledger/schema is compatible; otherwise it returns `503` with only `ok`/`failed` check names. `GET /health` remains an unauthenticated deprecated compatibility alias to `/health/live` for this release. | Route tests prove liveness does not contact dependencies, readiness returns `503` for each failed required check without secrets, and `/health` has the exact liveness result. Compose health checks use `/health/ready`. |
| Required versus optional configuration | Required for readiness: database URL/schema and `NUTRITION_INTERNAL_SERVICE_TOKEN`; main API readiness additionally requires a valid `NUTRITION_AGENT_URL` when `USE_NUTRITION_AGENT_SERVICE=true`. `USDA_FDC_API_KEY` and OpenAI configuration are optional: absence selects cache-only search and deterministic-only presentation respectively, and never makes readiness fail. Production startup rejects empty, placeholder, or known development values for required secrets and enabled optional integrations. | Configuration unit tests cover production rejection and both optional-dependency modes. |
| Rate limiting | Add `redis>=5` and `slowapi`. In production, Redis is mandatory and keys are `nutrition:{route}:{authenticated_user_id}`; local/test may use the explicitly configured in-memory backend. Limits per user: profile `30/min`, meal-log writes `60/min`, target calculation/save and meal-plan generation `20/min`, food search/detail `60/min`, assessment history `30/min`; all other nutrition reads `120/min`. Return `429 RATE_LIMITED` in the Section 1.1 envelope and integer `Retry-After` seconds. | Route tests verify key scope, each limit class, envelope, and header; deployment readiness/config test rejects production without Redis. |
| Logging, metrics, tracing, and request IDs | Use the current project logging approach for this implementation phase: Python `logging` with module loggers, explicit redaction, and request-ID propagation. Do not introduce a mandatory new logging framework such as `structlog` in this phase. Implement observability through centralized middleware/client wrappers so OpenTelemetry can be added later without rewriting business logic. Optional OpenTelemetry integration may be added behind disabled-by-default flags (`OTEL_ENABLED=false`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`). Metrics/tracing exporters and `/metrics` are optional unless explicitly enabled by configuration or a later production-readiness decision; if enabled, they must be private/network-restricted. Metric/span attribute names must be bounded and non-sensitive. | Tests verify redaction, request-ID propagation, bounded telemetry labels/attributes, and unchanged behavior when optional OpenTelemetry is disabled. |
| Client resilience | `docs/nutrition_agent/API-CONTRACT.md` is the sole authority for Nutrition Agent client timeouts, connection-pool limits, retries, circuit breaking, and public dependency-error mapping. Implement its lifecycle-managed async-client policy exactly. `docs/nutrition_agent/OPERATIONS.md` is authoritative for route-versus-chat fallback behavior. No programmatic route fabricates nutrition data or locally mutates after a dependency failure. | Mocked-client tests cover every canonical timeout/status, retry eligibility, breaker transition, public error mapping, and route-specific fallback. |
| Food-data bounds and cache | `API-CONTRACT.md` is authoritative for public food-search validation and response semantics: normalized `q` is 1–100 characters; `limit` defaults to 20 and caps at 50; detail IDs are positive integers; and responses use its `source`, `upstream_status`, and `stale` fields. This plan owns operational cache and upstream controls: USDA requests use its canonical client timeout, at most 30 outbound requests/minute/service instance, 1,000 outbound requests/hour/service instance, and 10,000 outbound requests/day/service instance. Per-instance counters and breaker state intentionally do not provide a global multi-instance quota; production capacity planning must multiply these ceilings by replica count. Successful normalized food details and search-result projections are fresh for 30 days. Stale results may be served only on upstream error/timeout/no-key conditions for up to 180 days, with the API-contract `stale=true` response field. Failed-refresh and no-result suppression lasts 15 minutes per normalized query or FDC ID. No key means cache-only operation. | Repository/service tests cover canonical public validation/metadata plus fresh hit, stale fallback, miss, suppression, malformed data, minute/hour/day quota, timeout, and no-key modes. |
| Data and payload bounds | JSON bodies are limited to 64 KiB at the main API. Meal description is trimmed plain text, 1–1,000 characters, with controls rejected; no HTML is rendered from it. Allergy/restriction arrays have at most 20 normalized entries of 1–80 characters. Calories are `0–10,000`; each macro gram value is `0–2,000`; when calories and macros are supplied, calculated macro calories must be within 20% of calories or return `422 NUTRITION_VALUE_INCONSISTENT`. History/list date ranges are at most 31 calendar days. | Schema and database-constraint tests cover each boundary and normalization rule. |
| PostgreSQL test isolation | Repository/integration tests use `NUTRITION_TEST_DATABASE_URL` only. CI starts PostgreSQL 16 with disposable database `nutrition_test`; its schema is `systemdb`, because immutable migrations `000`–`005` are schema-qualified to `systemdb`. The fixture fails before connecting if the URL is absent, is not database `nutrition_test`, or matches `DATABASE_URL`. It creates `systemdb`, applies migrations, truncates all `systemdb` tables with `RESTART IDENTITY CASCADE` between tests, and drops `systemdb` at session end. Developers must provide a disposable local test database; tests never create, migrate, truncate, or seed a developer/application database. | CI job logs database `nutrition_test` and schema `systemdb`; fixture guard tests reject unsafe URLs; clean and legacy-upgrade migration tests run against separate disposable databases. |

### Migration-ledger bootstrap protocol

Before any new nutrition migration, replace the rerun-all-files runner with the following protocol. The authoritative table is `systemdb.schema_migrations` with `version text primary key`, `filename text unique not null`, `sha256 char(64) not null`, and `applied_at timestamptz not null default now()`. Store lowercase SHA-256 values and enforce a three-or-more-digit version and 64-character lowercase hexadecimal hash using table check constraints.

1. Connect to an infrastructure-provisioned database with one dedicated connection, acquire one session-scoped PostgreSQL advisory lock before inspecting state, and retain that connection through checksum validation, legacy baselining, and every per-migration transaction. Release the lock in `finally` only after the complete run. Discover SQL files in lexical order and calculate SHA-256 from raw UTF-8 bytes.
2. For clean install only, execute `CREATE SCHEMA IF NOT EXISTS systemdb` before creating/reading the ledger. This is the sole bootstrap exception: the migration CLI must not create the PostgreSQL database, roles, or any other schema. Then create/read the ledger and apply `000`–`005` (and every later migration) in individual transactions, inserting each migration's version, filename, and checksum in the same transaction. Roll back the migration and ledger entry together on failure.
3. For an existing database with no ledger, verify the committed legacy `000`–`005` manifest before inserting any ledger entry. If and only if every verification passes, create the ledger and baseline *all* immutable `000`–`005` files with their current manifest checksums in one transaction without rerunning SQL. Abort with a clear operator-action error if verification is incomplete or ambiguous; never guess, repair, or baseline a partially applied database.
4. On every later migration run and on main-API/Nutrition-Agent compatibility validation, compare every ledgered file with the on-disk checksum before applying pending files. A missing file, changed checksum, duplicate version, out-of-order version, partial ledger, or schema-compatibility failure is fatal to migration/startup readiness and requires a new forward migration or explicit operator repair procedure. Historical migrations `000`–`005` are immutable.
5. Add only forward migrations beginning at `006`. The Nutrition Agent and main API remove runtime schema mutation: they may validate required tables, columns, constraints, indexes, and ledger state but may not create or alter them.

Create `C:\dev\multi-agent-coach\app\db\migrations\legacy_000_005_manifest.json` before enabling ledger baselining. It is committed immutable compatibility metadata containing the version, filename, and raw-byte SHA-256 for each historical file: `000_create_users_table.sql` / `a3765b1be23d2380953c107535de2978bf4d5992e4d2e5fbb6b48e8154980e86`; `001_create_tables.sql` / `19b99f88044e59a22fd5d3ca5002f182b7c97a1065b64fa1ce6e65748d63fd35`; `002_seed_data.sql` / `c52a8deab8d0a488261d9c7b8f705cc2dc32e13601cc75c8cab99694e137c2b1`; `003_create_recovery_tables.sql` / `a9ac41da3492b6c10ebb4ecca2cb8bd0560794ec0256e477c0378f654f64497e`; `004_create_nutrition_tables.sql` / `5df2119dfc4bb3f94e1baed1fc4260cfe782f763f77f59699944b4428af3ec75`; and `005_seed_food_cache.sql` / `7eb74f453ea3f340bbb73629f962911c04917060a9a2b7aca7d41d57a16b72aa`.

The manifest must require the `systemdb` schema; essential `users` and `user_fitness_profiles` columns, keys, constraints, and indexes; read-only existence checks for historical `003` recovery objects/keys/indexes; and all Nutrition `004` objects, essential columns, keys, constraints, and indexes (`nutrition_profiles`, `meal_logs`, `nutrition_assessments`, `food_cache`). Migration `002` is reference-only/no-op SQL and is validated only by its immutable filename/checksum, not by an asserted admin user. `005` must have exactly **220** `food_cache` rows (its historical comment stating 200 is inaccurate and must not be edited), unique `fdc_id` values spanning `1001` through `8010`, and a committed canonical content fingerprint.

Define the food-cache fingerprint in the manifest and runner as SHA-256 of compact UTF-8 JSON for the list ordered by `fdc_id`; each row is the ordered JSON array `[fdc_id,name,brand,serving_size_g,calories,protein_g,carbs_g,fat_g,fiber_g,category]`. Use `null` for SQL nulls, separators `(',', ':')`, and plain non-exponent decimal rendering with insignificant trailing zeroes removed (zero is `0`). Generate and commit the expected digest once from a clean install; use the same implementation for clean-install and legacy-baseline verification. Do not fingerprint SQL whitespace or database-specific display formatting.

Migration ownership is a single one-shot `python -m app.db.migrate` job/CLI, run exactly once per deployment before the Nutrition Agent and main API are rolled out. It is the only production/staging component this plan permits to mutate the shared `systemdb` schema. The historical `003` check proves shared migration ordering only and does not assign Recovery implementation work. The main API and Nutrition Agent run connection plus compatibility validation at startup/readiness and must not invoke the migration command, create tables, or alter schemas. Local development and CI invoke the same command explicitly against disposable databases. Compose/deployment starts an infrastructure-provisioned database, completes the migration job, then starts the Nutrition Agent and main API; both return readiness `503` until compatible ledger/schema state exists.

Database creation/provisioning is an infrastructure concern and is not performed by the migration CLI or a service process. Replace main-API `init_db()` startup behavior with connection and ledger/schema compatibility validation only; it must no longer call `setup_database()` or `run_migrations()`. The existing idempotent admin-user seed runs only as an explicit, separately invoked one-shot seed job after the migration job, never as part of service startup. Update or replace `seed_database()` so it cannot invoke the legacy migration runner or bypass the ledger protocol.

Required migration evidence is: clean install performs only the `systemdb` bootstrap exception then applies `000`–latest once; a legacy database matching the manifest baselines without rerunning SQL then applies `006+`; a rerun changes nothing; edited historical files, missing required objects/indexes, altered food-cache values/counts, or partial ledgers fail before ledger mutation; concurrent runners serialize on the advisory lock; and main API/Nutrition-Agent startup cannot issue schema-mutating DDL.

---

## 2. Current-State Findings

| Area | Status | Evidence | Required outcome |
|---|---|---|---|
| Private nutrition service | Partial | `C:\dev\multi-agent-coach\services\nutrition_agent\app\main.py` has health, profile upsert, meal creation, history, and evaluate endpoints. | Expand internal contract for all required operations and test it. |
| Main application integration | Partial / disabled by default | `C:\dev\multi-agent-coach\app\config.py:Settings` defaults `USE_NUTRITION_AGENT_SERVICE` to `False`; `NutritionAgentClient` only calls `evaluate`. | Add authenticated public routes and complete client methods; enable deliberately in deployment. |
| Persistence | Partial | Tables are defined in `004_create_nutrition_tables.sql`; runtime `NutritionRepository.ensure_schema()` duplicates DDL. | Add forward-only schema evolution, indexes, and repository methods; make migrations authoritative. |
| Nutrition history and adherence | Partial | `NutritionRepository.get_history()` calculates averages per log row and `main.py:get_history()` hard-codes `adherence_percentage=None`. | Aggregate by day and compare with approved calorie/macro targets. |
| TDEE and macro tools | Implemented but unused | `calculate_tdee()` and `calculate_macro_targets()` are not called by the service endpoint. | Expose and integrate safe deterministic target calculation. |
| Food data | Partial / unwired | USDA client and cache-read methods exist but no endpoint orchestrates cache-first search or cache writes. | Implement cache-first search/details, external fallback, and safe caching. |
| Meal planning | Partial / unsafe filtering gap | `generate_meal_plan()` uses static templates and explicitly does not implement allergy handling. | Filter allergens/restrictions; make generated plans available through a contract. |
| Safety controls | Partial | Medical-risk, eating-disorder, BMI, and calorie checks exist in `assess_nutrition()`. LLM success output does not enforce disclaimer preservation. | Add structured safety findings, broaden tests, guarantee response safeguards, and audit all target-generation paths. |
| Test coverage | Missing for nutrition | `C:\dev\multi-agent-coach\tests\test_recovery_assessment.py` is the closest pattern; no nutrition counterpart exists. | Add unit, route/client, integration, and regression tests. |

---

## 3. Target Architecture and Request Flow

```text
Authenticated browser/client
  -> Main API: /api/nutrition/* (JWT; derives user_id from current_user)
  -> NutritionAgentClient (internal HTTP token; timeout/error mapping)
  -> Nutrition Agent: /v1/nutrition/* (private Docker network/service token)
  -> PostgreSQL systemdb nutrition tables
  -> Optional USDA FoodData Central (only through Nutrition Agent)

Chat flow
  -> app.services.agent_service.specialist_node_api()
  -> NutritionAgentClient.evaluate()
  -> deterministic assess_nutrition()
  -> NutritionAgent.present() presentation only
```

### Ownership and trust boundaries

- The public API must never accept a user ID as an authority. It derives it from `get_current_user`.
- The main API is the only caller of internal nutrition endpoints in normal deployment.
- The internal service validates `X-Internal-Service-Token` on every non-health endpoint.
- The nutrition service owns nutrition persistence and never trusts an arbitrary profile field sent by a caller over persisted user data without schema validation.
- The deterministic assessment decides `status`, `score`, recommendations, and safety escalation. The LLM may only rewrite the approved presentation while preserving mandatory safety content.

---

## 4. Objective-to-Code Traceability Matrix

New function names below are implementation targets; exact signatures may be refined while retaining the described contract.

| Objective | Current implementation | Required files and functions/routes | Completion evidence |
|---|---|---|---|
| Authenticated public nutrition API | Missing | **Add** `C:\dev\multi-agent-coach\app\api\routes\nutrition.py`: `get_profile`, `upsert_profile`, `create_meal_log`, `list_meal_logs`, `get_meal_log`, `update_meal_log`, `delete_meal_log`, `get_history`, `get_assessment_history`, `get_assessment`, `calculate_targets`, `save_target`, `generate_meal_plan`, `search_foods`, `get_food_detail`; **modify** `C:\dev\multi-agent-coach\app\main.py` router import/`app.include_router`; **add** public schemas in `C:\dev\multi-agent-coach\app\api\schemas\nutrition.py` or the established schema location. | JWT route tests prove user identity is derived server-side and data is isolated. |
| Profile management | Partial | Existing `C:\dev\multi-agent-coach\services\nutrition_agent\app\main.py:create_or_update_profile`; existing `...\repository.py:NutritionRepository.create_or_update_profile`, `get_profile`; **add** internal `get_profile` route and `NutritionAgentClient.get_profile`, `upsert_profile`. | Create, update, and retrieve profile through public API; unknown/malformed values rejected. |
| Meal logging and retrieval | Partial | Existing `...\main.py:create_meal_log`; `...\repository.py:create_meal_log`; **add** `NutritionRepository.list_meal_logs`, `get_meal_log`, `update_meal_log`, and `delete_meal_log`; **add** corresponding internal routes and client methods. | User can create/list/read/update/delete own logs; dates/pagination validated; cross-user attempts cannot access records. |
| History and adherence | Partial | Existing `...\repository.py:get_history`, `...\main.py:get_history`, `...\assessment.py:NutritionHistory`; **modify** all three; **add** deterministic adherence calculation helper(s), daily aggregate repository query, and target comparison. | Known daily fixture returns expected averages and adherence; no target returns `null`, not fabricated adherence. |
| Assessment and safety | Partial | Existing `...\assessment.py:assess_nutrition`, `_check_medical_risk`, `_check_eating_disorder_keywords`, `_calculate_bmi`; existing `...\agent.py:NutritionAgent.present`; **add** request-scoped typed safety context, structured safety finding schema, and disclaimer-preserving presentation validation. | Structured/phrase-derived risk always returns `escalate`; raw safety context is not persisted; safe outputs cannot lose disclaimer; prompt injection does not override assessment. |
| TDEE and macro targets | Implemented but unused | Existing `...\tools\tdee_calculator.py:calculate_bmr`, `calculate_tdee`; `...\tools\macro_targets.py:calculate_macro_targets`; **add** typed request/response schemas, internal route(s), `NutritionAgentClient.calculate_targets`, and evaluation wiring where sufficient profile data exists. | Formula and guardrail unit tests; public request returns target and calculation metadata. |
| Meal plans respecting preferences/allergies | Partial | Existing `...\tools\meal_planner.py:generate_meal_plan`; **modify** it to enforce allergies/restrictions and validate dietary preference; **add** plan route/client contract. | Tests verify allergen exclusion and no unsupported target can create an unsafe plan. |
| Food cache and USDA fallback | Partial | Existing `...\tools\food_database.py:FoodDatabaseClient.search_food`, `get_food_details`, `search_and_get_details`; existing `...\repository.py:search_food_cache`, `get_cached_food`; **add** `upsert_cached_food`, cache-first orchestration service, search/details routes, and client methods. | Tests prove cache is consulted first, USDA errors fall back cleanly, and external results are normalized before caching. |
| Assessment history | Persistence only | Existing `...\repository.py:save_assessment`; **add** `list_assessments` and internal/public read routes; add pagination response schema. | Latest-first, user-scoped history with bounded page size and no sensitive internals leaked. |
| Chat integration | Partial | Existing `C:\dev\multi-agent-coach\app\services\agent_service.py:specialist_node_api`; existing `...\nutrition_agent_client.py:NutritionAgentClient.evaluate`; existing `C:\dev\multi-agent-coach\app\config.py:Settings`. | Enabled service path succeeds; timeout/5xx falls back predictably and records safe log metadata. |
| Runtime/deployment configuration | Partial | **modify** `C:\dev\multi-agent-coach\docker-compose.yml`, `C:\dev\multi-agent-coach\.env.example`, `C:\dev\multi-agent-coach\app\config.py:Settings`, `C:\dev\multi-agent-coach\services\nutrition_agent\app\config.py:Settings`. | Compose deployment has consistent token/URL values, no committed real USDA key, and nutrition service is intentionally enabled. |
| Database evolution | Partial | Existing `C:\dev\multi-agent-coach\app\db\migrations\004_create_nutrition_tables.sql`, `005_seed_food_cache.sql`; **add** next forward-only migration; **modify** `...\repository.py:ensure_schema` to avoid divergent schema ownership. | Fresh and upgrade databases produce matching schemas; migration is idempotent where required. |
| Documentation and API reference | Partial | **modify** `C:\dev\multi-agent-coach\docs\API-REFERENCE.md`, `C:\dev\multi-agent-coach\README.md`, `C:\dev\multi-agent-coach\services\nutrition_agent\README.md`, and `.env.example`. | Documented public endpoints match OpenAPI and tested behavior. |
| Automated validation | Missing | **add** `C:\dev\multi-agent-coach\tests\test_nutrition_assessment.py`, `test_nutrition_tools.py`, `test_nutrition_routes.py`, `test_nutrition_agent_client.py`; add service integration tests following repository conventions. | `pytest` suite passes; integration tests run against an isolated test database/service. |

---

## 5. API Contract Plan

### Public main-API endpoints

All routes are registered at `C:\dev\multi-agent-coach\app\main.py` under `/api`, require the existing JWT dependency, and infer the user ID from `current_user`. Section 7.1 is the authoritative endpoint contract and supersedes any older route/method alternatives.

### Contract rules

- Validate page sizes and query lengths at the Pydantic boundary.
- Return `404` for a missing profile/resource only where absence is exceptional; return an empty collection for no meal logs or assessments.
- Do not expose `tool_trace`, raw internal error bodies, service tokens, upstream API keys, or unredacted medical-risk matching terms through ordinary history responses.
- Use the Section 1.1 stable error envelope; document status codes and error codes for every endpoint.
- Keep `/v1/nutrition/*` private. Only `/health/live`, `/health/ready`, and the deprecated `/health` compatibility alias are unauthenticated, with the exact Section 1.1 behavior.

---

## 5.1 Implementation Readiness Packs

These packs turn the distributed binding defaults into implementable prerequisites. They are required preparation for an uninterrupted end-to-end development effort, but do not replace the validation and user-facing-release gates elsewhere in this plan. Complete a pack's entry criteria before beginning dependent work. Record a dated decision in Section 14 for any accepted deferral or deviation.

### Pack A — Contract freeze

**Purpose:** Prevent public/internal API, safety, and orchestrator integration rework caused by changing payloads or validation semantics mid-implementation.

**Required solution:**

- Use `API-CONTRACT.md` as the canonical contract inventory and Section 7.1 as the authoritative route table. For every public and internal operation, specify its method/path, authenticated identity source, typed request/query/path fields, response schema, pagination/date bounds, error status/code, rate-limit class, and dependency fallback.
- Implement one typed schema source per service boundary. Public handlers derive `user_id` only from the authenticated user; the trusted main API supplies it only to the private internal contract.
- Apply the Section 1.1 public error envelope consistently. Reject unknown enums and out-of-range values at the Pydantic boundary; do not leave implicit defaults that change safety, ownership, or persistence behavior.
- Freeze calculate-only versus target-save semantics: calculation routes never mutate state, and target-save creates an immutable version with effective dates.
- Define the typed user-safe `safety_findings` and `escalation` projection, including allowed codes, severity/order, and `null` behavior. The request-scoped safety-context allowlist, stable deduplication order, and non-persistence/non-logging rules must be stated in `SAFETY-POLICY.md`.
- Freeze the `NutritionAgentClient` request/response models used by the orchestrator only after the corresponding internal contracts are complete. Service failure and disabled-rollout fallback must return to the existing local specialist path without exposing internal details.

**Entry criteria for dependent implementation:** the endpoint table, typed safety projection, error envelope, target versioning contract, and orchestrator fallback behavior are documented and have no unresolved decisions.

### Pack B — Schema authority and data evolution

**Purpose:** Ensure development never depends on runtime schema mutation and that clean installs and upgrades follow one authoritative path.

**Required solution:**

- Make the Section 1.1 transactional migration ledger/bootstrap protocol the sole schema authority before adding nutrition migrations beyond immutable `000`–`005`.
- Implement schema compatibility/readiness validation first. It must report a clear unhealthy/incompatible result for a missing or mismatched schema and must not create or alter application tables.
- Then remove duplicate runtime DDL from `NutritionRepository.ensure_schema`. Do not modify immutable applied migrations; add forward-only `006+` migrations for targets, indexes, cache freshness metadata, and structured safety fields.
- Document the clean-install and legacy-baseline upgrade sequence in `MIGRATION-RUNNER.md`, including fatal checksum-mismatch behavior and the required operator action for an incompatible schema.
- Configure the one-shot migration job to finish before application startup. Both the main API and Nutrition Agent perform validation-only startup/readiness checks.

**Entry criteria for persistence-dependent implementation:** migration ledger behavior, immutable legacy manifest, schema compatibility contract, forward-migration ownership, and upgrade operational procedure are documented with no ambiguity.

### Pack C — USDA operations and credential governance

**Purpose:** Make food-search behavior deterministic and safe whether USDA is healthy, unavailable, rate-limited, or intentionally disabled.

**Required solution:**

- An authorized credential owner rotates/revokes the exposed USDA credential and records the ticket/attestation and repository-history decision without recording a secret value. Remove all tracked credential values from code, Compose, examples, and documentation; accept the replacement only through approved environment/secret management. CI secret scanning must block verified secrets.
- Publish the normalized internal food-cache model before implementing `upsert_cached_food`; raw USDA responses are never persisted or returned as the application contract.
- Document and implement one cache-first outcome matrix: cache hit; cache miss with successful USDA normalization/upsert; stale cache with failed refresh; timeout/quota/network failure; malformed upstream payload; and no configured USDA key. Cache-only/no-key mode remains usable for valid cached data and returns bounded typed metadata rather than raw upstream errors.
- Configure and document the binding cache TTL, stale-serve window, failed-refresh/no-result suppression window, result/payload bounds, USDA timeouts, quotas, and circuit-breaker settings from Section 1.1. Suppression is separate from quota enforcement.
- Make all food-search/detail endpoints bounded and rate-limited, and ensure logs/metrics never include keys, raw upstream payloads, or sensitive user input.

**Entry criteria for USDA-dependent implementation:** credential governance ownership is assigned, the no-key/cache-only response behavior and normalized cache shape are frozen, and the cache/outage behavior matrix is documented.

### Pack D — Sequencing and delivery gates

**Purpose:** Prevent cross-phase churn by completing shared foundations before vertical slices and holding user enablement behind the existing release gates.

**Binding implementation order:**

During the active 2026-08-31 development-core pass, Section **Development-core execution order** is the sole binding sequence and supersedes this historical cross-phase order. In particular, implement migration-ledger/readiness behavior and validation-only application startup, but defer one-shot migration deployment wiring, Compose, and seed jobs. Implement the core schema, safety, persistence, private-route, public-programmatic-route/client, and chat/orchestrator work in that order. Do not begin rate-limit infrastructure, observability rollout, tests, CI, deployment, or rollout/rollback work in this pass.

For a later operational and release pass, complete the following order:

1. Confirm Pack A's contract and safety-policy artifacts and Pack B's migration-authority prerequisites remain current.
2. Add and validate one-shot migration deployment wiring before persistent Nutrition changes are deployed.
3. Complete production cache/USDA resilience after Pack C's credential-governance and operational behavior are approved.
4. Complete deterministic rollout controls, observability, documentation, deployment/rollback wiring, and the remaining release evidence; keep rollout disabled or at `0` until release gates pass.

**Phase entry criteria:**

- Phase 1/2 routes may begin only after Pack A defines their request/response and error contracts.
- Phase 3 and every persistence feature may begin only after Pack B defines migration ownership and compatibility behavior.
- Phase 4 requires the target, timezone, daily aggregation, adherence-nullability, and meal-constraint semantics in Section 1.1 to remain unchanged or to have an approved Section 14 decision.
- Phase 5 development-core work may begin after the normalized cache model and cache-only/no-key/outage behavior are frozen. Credential-owner attestation, CI secret scanning, quotas, and rate-limit infrastructure remain production/user-facing-enable gates.
- Phase 6 chat enablement may begin only after typed safety outputs and the safe local-fallback contract are complete.
- Phase 7/8 release work may begin after all implemented capabilities have matching contracts, deployment configuration, and operational documentation.

**Development-complete gates (testing may be scheduled separately, but cannot be claimed as passed):**

- Every intended capability has a complete vertical path: typed schema, private route, repository/service operation, `NutritionAgentClient` method, and—where required—ownership-safe public route and chat integration.
- Application services make no runtime DDL changes; the migration job is the only schema mutator and readiness reports schema incompatibility clearly.
- No real credential may be introduced into a tracked file. Development uses environment-provided or blank/cache-only configuration; secret-manager enforcement, credential attestation, CI secret scanning, and production placeholder/default validation remain later release requirements.
- Disabled service, rollout `0`, service timeout/5xx, and USDA no-key/outage paths have documented safe fallback behavior.
- Implemented schemas, configuration names, route contracts, and safe fallback behavior reflect the development-core implementation. Operational documentation and rollout/rollback instructions remain later release work. Items awaiting later test execution remain `[ ]` or `[~]`; do not mark them `[x]` without their stated validation evidence.

### Readiness-pack checklist

- [x] Pack A: Publish and freeze canonical API, target-versioning, typed safety, validation/error, and orchestrator-fallback contracts.
  - **2026-08-30:** Published `API-CONTRACT.md`, `SAFETY-POLICY.md`, `TESTING.md`, and `ROLLOUT.md` as the canonical implementation contracts for route schemas/errors, target save/calculate semantics, typed safety policy, and orchestrator fallback/rollout behavior. Implementation remains pending.
- [x] Pack B: Establish migration ledger/schema-compatibility authority, legacy upgrade procedure, and validation-only service startup before forward nutrition schema work.
  - **2026-08-30:** Published `docs\nutrition_agent\MIGRATION-RUNNER.md` with command ownership, ledger format, legacy baseline, advisory lock, clean-install/upgrade behavior, failure handling, and required tests. Implementation remains pending.
- [x] Pack C: Complete USDA credential-governance preparation and publish normalized cache plus no-key/outage/cache-policy behavior.
  - **2026-08-30:** Credential-owner attestation remains an external release gate, but operational no-key/outage/cache behavior is documented in `OPERATIONS.md`, `TESTING.md`, and `ROLLOUT.md` for implementation.
- [x] Pack D: Apply the binding implementation sequence and phase entry criteria; track each deviation or blocker in Section 14.
  - **2026-08-30:** Published operations, testing, rollout, and migration contracts; no sequencing deviations recorded.

---

## 6. Master Checklist

### Phase 0 — Baseline and implementation decisions

- [x] Record binding defaults for nutrition-only token naming, API conventions, meal-log behavior/idempotency, retention, target versioning, daily history/adherence, safety behavior, and profile concurrency in Section 1.1.
- [x] Inventory every Nutrition-related uncommitted scaffold change before modifying implementation code. Record each file and its disposition (`retain`, `rewrite`, or `revert`) in Section 14; only retained code may be used as a starting point, and it must still conform to the canonical contracts.
- [x] Create `C:\dev\multi-agent-coach\docs\nutrition_agent\` and skeleton docs for `API-CONTRACT.md`, `SAFETY-POLICY.md`, `MIGRATION-RUNNER.md`, `OPERATIONS.md`, `TESTING.md`, and `ROLLOUT.md`.
  - **2026-08-30:** Created and subsequently completed the Phase 0 contract documents. Implementation and validation remain pending in later checklist items.
- [x] Merge implementation-readiness defaults into Sections 1.1, 6, 9, 12, and 13, then remove duplicated or superseded text.
  - **2026-08-30:** Consolidated the implementation-readiness defaults into the authoritative sections, removed the superseding defaults appendix, replaced stale cross-references, and verified no active Section 15 dependency remains. Implementation, migration, documentation, and tests remain required in later phases.
- [-] Obtain written product, privacy, and safety-owner approval for the binding defaults in Section 1.1 before any production/user-facing release. Evidence must identify approver, date, approved retention/hard-delete and safety/referral behavior, and every accepted deviation; link it in Section 14.
  - **2026-08-30:** Deferred for production release under development-first mode. Development proceeds with `nutrition-safety-v1`; production enablement remains blocked until approval evidence is recorded.
- [-] An authorized USDA credential owner must revoke/rotate the credential exposed in tracked history/configuration and store its replacement only in approved secret management. Record rotation ticket/attestation and date (never the value), remove the exposed value from every tracked file and documentation, and add CI secret scanning that fails on verified secrets. This gate cannot be completed by deleting the tracked value alone.
  - **2026-08-30:** Deferred for production release under development-first mode. Current tracked files no longer contain the exposed key; development uses blank/cache-only `USDA_FDC_API_KEY` or a developer-provided local environment value.
- [ ] Add and pin the confirmed required rate-limit, Redis, request-ID/redaction, resilience, and secret-scanning tooling in the applicable dependency manifests and CI. The implementation must wire the selected Redis-backed limiter (including `slowapi` if retained as the chosen framework), Redis client support, and `gitleaks`; optional telemetry/exporter packages remain out of scope unless explicitly enabled.
- [ ] Implement the isolated `NUTRITION_TEST_DATABASE_URL` fixture and CI PostgreSQL 16 service. Add fail-closed URL guards and prove repository/migration tests cannot connect to `DATABASE_URL`, an unset test URL, or a database other than `nutrition_test`.
- [ ] Implement the Section 1.1 transactional migration ledger/bootstrap protocol before any nontrivial nutrition schema change. Preserve `000`–`005`, then add only `006+` migrations after clean-install, legacy-baseline, checksum-failure, and concurrent-runner tests pass.
- [x] Complete the Section 7.1 endpoint-contract table for every public/internal route, including request/query/path schema, success and stable error codes, pagination/date bounds, rate-limit class, and documented dependency fallback.
  - **2026-08-30:** Published the canonical route, schema-name, stable-error, rate-limit, pagination/date, and fallback contract in `C:\dev\multi-agent-coach\docs\nutrition_agent\API-CONTRACT.md`; Section 7.1 now points to that file as the implementation source. Public API-reference examples remain a rollout documentation requirement.
- [x] Establish baseline commands and record their result in a dated note:
  - `uv run pytest -q`
  - nutrition-service test command after tests are added.
  - **2026-08-30:** Ran `uv run pytest -q`; result `6 passed`. Nutrition-service-specific test command is documented in `docs\nutrition_agent\TESTING.md` and will become runnable after tests are added.

### Phase 1 — Public API foundation and identity safety

- [x] Add `C:\dev\multi-agent-coach\app\api\routes\nutrition.py` with an `APIRouter` following `chat.py` and `session.py` conventions.
- [x] Add public request/response schemas in `C:\dev\multi-agent-coach\app\api\schemas\nutrition.py` (or the confirmed existing schema module convention).
- [x] Register the router in `C:\dev\multi-agent-coach\app\main.py` using `app.include_router(nutrition.router, prefix="/api", tags=["Nutrition"])`.
- [x] Ensure every public handler uses `get_current_user` and derives `user_id`; never accept public `user_id` input. Apply the Section 1.1 error envelope, date/timezone, and offset-pagination conventions.
- [x] Add public API tests for authentication, validation, and cross-user isolation.
  - **2026-09-02:** `tests\nutrition\test_public_nutrition_boundary.py`, `test_food_routes.py`, `test_assessment_history.py`, and `test_target_versioning.py` pass in the isolated main-application test process (`165 passed, 1 skipped`).

### Phase 2 — Internal contract and client completion

- [x] Keep service-token enforcement in `C:\dev\multi-agent-coach\services\nutrition_agent\app\main.py:require_internal_token` for existing protected endpoints.
- [x] Add internal read/list/update/delete routes in `...\services\nutrition_agent\app\main.py` for profile, meal logs, assessments, food search, targets, and meal plans.
- [x] Extend `C:\dev\multi-agent-coach\services\nutrition_agent\app\schemas.py` with typed pagination, target, meal-plan request, `NutritionSafetyContext`, and safety-finding models. Put request-scoped safety context only on evaluation/target/plan requests, never on persistent profile models.
- [x] Extend `C:\dev\multi-agent-coach\app\services\nutrition_agent_client.py:NutritionAgentClient` with methods matching each internal operation.
- [x] Implement a reusable async `httpx.AsyncClient` managed by FastAPI lifespan, with connection pooling and separate connect/read/write/pool timeouts. Add stable error mapping without leaking response details to users, and propagate `X-Request-ID`.
- [ ] Add unit tests with mocked `httpx` for every client method and failure category.

### Phase 3 — Profiles, meal logs, and persistence

- [x] Preserve existing profile upsert in `...\services\nutrition_agent\app\main.py:create_or_update_profile` and `...\repository.py:NutritionRepository.create_or_update_profile`.
- [x] Add an internal profile retrieval route over `NutritionRepository.get_profile` and normalize a missing profile response.
- [x] Preserve existing meal creation in `...\services\nutrition_agent\app\main.py:create_meal_log` and `...\repository.py:NutritionRepository.create_meal_log`.
- [x] Add `NutritionRepository.list_meal_logs` date-range filtering with parameterized SQL, newest-first ordering, bounded offset pagination, and IANA timezone-local day bounds.
- [x] Add ownership-preserving `update_meal_log` and `delete_meal_log` repository/routes/client methods using the Section 1.1 full-replacement and hard-delete contract.
- [ ] After the Phase 0 ledger gate passes, create forward-only `006+` migration(s) for log metadata, target persistence, safety fields, and indexes. Do not rewrite applied migrations; verify the Section 1.1 clean-install and legacy-baseline upgrade paths.
- [x] Remove duplicate runtime DDL from `NutritionRepository.ensure_schema`; the migration ledger is the schema authority. The Nutrition Agent readiness check must report an incompatible/missing schema rather than creating application tables.
- [ ] Test profile persistence, meal-log persistence, ordering, and user isolation against an explicitly provisioned disposable PostgreSQL database. Unit coverage now verifies meal-log date filtering and validation.

### Phase 4 — Deterministic calculations, history, and plans

- [x] Retain `...\tools\tdee_calculator.py:calculate_bmr` and `calculate_tdee` as the deterministic Mifflin-St Jeor implementation.
- [x] Add validation for the target-calculation inputs (age, height, weight, activity level, supported goal) before calling `calculate_tdee`.
- [x] Retain `...\tools\macro_targets.py:calculate_macro_targets` minimum-calorie controls.
- [x] Validate target calculations for all genders and ensure targets cannot silently produce negative carbohydrate values or invalid macro percentages.
  - **2026-09-02:** Normalized prescribed protein/fat proportionally when they exceed the calorie target, producing zero rather than negative carbohydrates. Percentages are calculated from final rounded macro grams and rejected unless finite, non-negative, bounded, and normalized. Regression coverage exercises every supported gender and goal plus high-weight calorie-floor cases.
- [x] Add a typed calculation service/route that returns TDEE metadata plus macro targets without mutation, and a separate explicit target-save route that persists the immutable versioned target required by Section 1.1.
- [x] Modify `NutritionRepository.get_history` to aggregate daily totals, not individual meal-log rows.
- [x] Add deterministic adherence calculation against approved calorie/macro targets and return `null` when no target or insufficient comparable data exists.
- [x] Wire completed target data into `assess_nutrition` only after adherence semantics are tested.
- [x] Modify `...\\tools\\meal_planner.py:generate_meal_plan` to filter dietary restrictions and allergies; reject/return safe no-plan responses when templates cannot satisfy constraints.
  - **2026-09-02:** Static templates use internal ingredient tags rather than meal display text for matching. Every selected category must retain a safe option; otherwise the route emits the policy's generic `OTHER_MEDICAL_CONDITION` referral without disclosing the failed exclusion.
- [x] Expose a typed meal-plan operation and tests proving restrictions/allergies are honored.
- [x] Add unit tests for BMR/TDEE, macro targets, daily history, adherence, and meal plans.

### Phase 5 — Food search, cache behavior, and USDA resilience

- [x] Retain cache read methods `NutritionRepository.search_food_cache` and `NutritionRepository.get_cached_food`.
- [x] Add `NutritionRepository.upsert_cached_food` with normalized USDA data and parameterized SQL.
- [x] Add a cache-first food-search orchestration function/service: local search, USDA fallback only when needed, normalization, then cache update.
- [x] Add bounded and validated food-search/detail internal and public endpoints.
- [ ] Implement the Section 1.1 food-cache TTL, stale-result, suppression, USDA timeout/quota, payload-bound, and cache-only/no-key behavior.
- [ ] After the Phase 0 credential rotation, remove the committed USDA API key from `...\services\nutrition_agent\app\config.py`, `docker-compose.yml`, and documentation; use environment-only configuration and verify no tracked file retains it.
- [ ] Test cache hit, cache miss/upstream success, upstream timeout/error, malformed upstream payload, and no-USDA-key behavior.

### Phase 6 — Safety, presentation, and chat integration

- [x] Preserve medical emergency escalation in `...\assessment.py:_check_medical_risk` and `assess_nutrition`.
- [x] Preserve eating-disorder signal escalation in `...\assessment.py:_check_eating_disorder_keywords` and `assess_nutrition`.
- [x] Add a typed, user-safe `safety_findings`/`escalation` response field rather than relying only on prose and `tool_trace`.
- [x] Add the Section 1.1 bounded structured safety-context contract to evaluate, target, target-save, and meal-plan schemas/routes. Reject unknown enum values, deduplicate valid conditions in stable policy order, and ensure request-scoped values cannot enter persistence, logs, tool traces, responses, or metric labels.
- [ ] Audit `_calculate_bmi`, low-calorie, and requested rate-of-loss logic; ensure constants are used consistently and no contradictory threshold appears in docs/tool code.
- [x] Ensure every `NutritionAgent.present` success, disabled-LLM, missing-key, and exception path preserves the medical disclaimer; escalation paths must preserve the escalation warning.
  - **2026-08-31:** Presentation uses approved structured assessment fields, retains escalation referral text, and appends the deterministic disclaimer exactly once on all presentation and fallback paths.
- [x] Add output constraints/validation so LLM presentation cannot add medical claims, instructions to self-harm/restrict/purge, or prompt leakage.
  - **2026-08-31:** Unsafe generated prose containing prompt/secrets or self-harm, restriction, or purging terms is rejected in favor of deterministic safety-preserving text.
- [ ] Modify `C:\dev\multi-agent-coach\app\services\agent_service.py:specialist_node_api` to use a complete, validated nutrition profile and safely handle missing `user_id`/service failures.
- [x] Modify `C:\dev\multi-agent-coach\app\config.py:Settings` and deployment config to make nutrition-service enablement intentional and environment-specific.
- [ ] Test medical risk, eating-disorder signals, BMI boundaries, calorie boundaries, prompt injection, LLM fallback, disclaimer retention, and chat fallback.

**2026-09-02 reconciliation evidence:** Completed checklist items above were verified against the private/public routes, repository, schemas, migrations `006`–`008`, and client implementation. Focused regression coverage includes `tests/nutrition/test_private_safety_wiring.py`, `test_nutrition_safety_policy.py`, `test_nutrition_agent_client_resilience.py`, `test_public_nutrition_boundary.py`, `test_food_reference.py`, `test_food_routes.py`, `test_repository_foundations.py`, `test_target_versioning.py`, and `test_chat_nutrition_service.py`. Items remain unchecked where the full stated contract or its required coverage is not yet present.

### Phase 7 — Assessment history, observability, docs, and rollout

- [x] Preserve assessment persistence through `...\repository.py:NutritionRepository.save_assessment`.
- [x] Add `NutritionRepository.list_assessments` with user filter, newest-first ordering, bounded pagination, and a redacted public projection.
  - **2026-09-01:** History reads only dedicated sanitized projection columns, scopes by user, orders deterministically newest-first, and supports bounded offset pagination.
- [x] Add internal/public assessment-history routes and tests.
  - **2026-09-01:** Added token-protected internal and authenticated public history routes with privacy, pagination, and ownership regression coverage.
- [ ] Add structured logs/metrics for internal call latency, error category, fallback usage, assessment status, USDA fallback, and safety escalation; never log service tokens or sensitive profile values unnecessarily.
- [x] Add the deterministic `NUTRITION_AGENT_ROLLOUT_PERCENT` cohort selection required by Section 1.1; cover disabled, `0`, `10`, `50`, and `100` percent routing, sticky user assignment, invalid configuration, and rollback to local fallback.
  - **2026-08-30:** Added deterministic SHA-256 rollout helpers in `app\services\nutrition_rollout.py`, orchestrator gating in `agent_service.py`, development config/defaults, and unit coverage for 0/10/50/100 boundaries, sticky bucket calculation, and invalid inputs.
- [x] Update `C:\dev\multi-agent-coach\.env.example` with all required nutrition settings and safe placeholders.
  - **2026-08-30:** Added `APP_ENV=development`, `NUTRITION_AGENT_ROLLOUT_PERCENT=0`, `NUTRITION_LLM_ENABLED=false`, separate nutrition token placeholder, and blank `USDA_FDC_API_KEY`.
- [x] Update `C:\dev\multi-agent-coach\docs\API-REFERENCE.md` with public endpoint contracts, authentication, examples, and errors.
  - **2026-09-03:** Added the authenticated public Nutrition route inventory, ownership boundary, private-service prohibition, error envelope, stable-code summary, and canonical-contract link.
- [x] Update `C:\dev\multi-agent-coach\README.md` and `C:\dev\multi-agent-coach\services\nutrition_agent\README.md` to distinguish implemented/validated behavior from future enhancements.
  - **2026-09-03:** Corrected the obsolete startup-DDL/migration claims, documented explicit migration prerequisites, and distinguished the development-core private service from deferred production/release work.
- [ ] Update `C:\dev\multi-agent-coach\docker-compose.yml` with consistent nutrition service enablement, environment-derived tokens/no exposed credentials, a one-shot migration job that completes before Nutrition Agent/main API startup, and validation-only application startup. Keep Nutrition Agent private; do not modify other-agent services as part of this plan.
- [ ] Fix `C:\dev\multi-agent-coach\services\nutrition_agent\Dockerfile` so it builds from tracked files: remove `COPY data ./data` unless a required tracked `services\nutrition_agent\data` directory is deliberately introduced and documented.
- [ ] Finalize all `docs\nutrition_agent` documents with shipped route contracts, safety policy, migration runner usage, testing commands, operations guidance, and rollout evidence.
- [ ] Run full regression, integration, and Docker smoke tests; attach dated result notes below this phase.
- [ ] Mark the release complete only after the Master Checklist plus Sections 9 and 10 are fully `[x]` or have explicit accepted `[-]` decisions.

### Phase 8 — Production hardening

- [ ] Complete or explicitly defer every required item in Section 9, including rate limiting, daily history/adherence semantics, meal-log CRUD, assessment history, food search/USDA resilience, client resilience, observability, readiness/liveness, validation/normalization, safety policy versioning, LLM safety hardening, expanded nutrition safety scope, performance/load targets, concurrency testing, and documentation consistency. Resolve the explicitly deferred API-level idempotency decision before production readiness.
- [ ] Add startup validation that rejects production mode when internal service tokens, USDA/OpenAI keys, service URLs, or other sensitive configuration use known dev/default values.
- [ ] Confirm production rate limiting uses the Section 1.1 Redis backend; in-memory rate limiting is allowed only for explicitly configured local development and tests.

---

## 7. Detailed Implementation Sequence

### Active development-core implementation sequence

For the active 2026-08-31 development-core pass, follow Section **Development-core execution order**; it is the authoritative replacement for the historical first-slice sequence. Begin with canonical typed schemas, deterministic `nutrition-safety-v1`, disclaimer enforcement, and safe/redacted assessment projections. Then implement migration-ledger/readiness and validation-only startup, ownership-scoped persistence, private routes, authenticated public programmatic routes/client methods, and chat/orchestrator integration.

Do not add or expand tests, fixtures, CI, Compose/deployment jobs, image/deployment remediation, credential rotation/attestation, secret scanning, Redis/rate limiting, observability rollout, load work, or rollout/rollback artifacts during this pass. Maintain cache-only/no-key behavior without introducing tracked credentials. These deferred items remain mandatory before pre-production or user-facing enablement.

### 7.1 Endpoint contract to approve before route implementation

The canonical route, schema, stable-error, rate-limit, and fallback contract is `C:\dev\multi-agent-coach\docs\nutrition_agent\API-CONTRACT.md`. That document is the implementation source for public routes, private Nutrition Agent routes, and main-API client methods. Changes to externally visible fields, paths, statuses, or fallback semantics require a Section 14 decision and an API-versioning assessment.

Required route families covered by the canonical contract:

- profile read, upsert, and hard delete;
- meal-log create/list/update/delete with idempotency and pagination;
- target calculation, explicit target save, and current target read;
- timezone-aware daily history and nullable adherence;
- safety-gated meal-plan generation;
- cache-first food search/details with no-key and outage metadata;
- assessment history pagination; and
- orchestrator/chat evaluation with disabled, rollout-0, timeout, and 5xx fallback.

Before rollout, `C:\dev\multi-agent-coach\docs\API-REFERENCE.md` must include request/response examples and stable error examples for every shipped public route.

### 7.2 Create the public router first

Add `C:\dev\multi-agent-coach\app\api\routes\nutrition.py` and register it in `C:\dev\multi-agent-coach\app\main.py`. Mirror the patterns in:

- `C:\dev\multi-agent-coach\app\api\routes\chat.py`
- `C:\dev\multi-agent-coach\app\api\routes\session.py`
- `C:\dev\multi-agent-coach\app\api\routes\auth.py:get_current_user`

Every public handler must set the effective `user_id` from `current_user["id"]` (or the confirmed current-user shape) when calling `NutritionAgentClient`. This avoids an insecure direct-object-reference vulnerability. Public/internal typed evaluation, target, target-save, and meal-plan models must carry the Section 1.1 request-scoped safety context; profile schemas must not.

Before a route is implemented, add its exact typed request/response model and an API-reference example. The models/examples must bind profile fields and enums; meal-log timestamps and canonical payload used for idempotency comparison; target version/effective-date behavior; history daily-item/freshness fields; assessment filters and redacted projection; food `source`, `cache_hit`, `stale`, and freshness fields; and every documented error code/status. No endpoint may be called complete based only on a route name or a prose description.

### 7.3 Expand internal routes and the client together

For every public capability, add the internal route in `services/nutrition_agent/app/main.py`, a typed schema in `services/nutrition_agent/app/schemas.py`, a repository/service operation, and a matching `NutritionAgentClient` method. Implement and test these as vertical slices rather than leaving routes that cannot reach a repository method.

### 7.4 Make data aggregation semantically correct

The present `NutritionRepository.get_history()` uses `AVG(calories)` across meal rows. That represents an average meal, not average daily intake. Replace it with daily aggregation for the requested period, then aggregate those day totals. Define whether missing-log days count as zero explicitly; the recommended initial behavior is to calculate only on logged days and return `null` adherence where the evidence is insufficient.

### 7.5 Only persist deliberate targets

`calculate_tdee()` and `calculate_macro_targets()` produce an immediate calculation without changing the profile. Ongoing adherence tracking uses the explicit persisted immutable target record/version required by Section 1.1 and created by `POST /api/nutrition/targets` in a forward migration. Never infer a target from an old chat message.

### 7.6 Implement cache-first food lookup

The caller should search local `food_cache` first. If it has no usable result, use `FoodDatabaseClient`, normalize the upstream response to the internal food schema, save it with `upsert_cached_food`, and return only normalized response data. Upstream failure should return cached results where possible or a controlled service response—not a raw `httpx` error.

### 7.7 Keep safety deterministic

`assess_nutrition()` remains the authority. The LLM presentation layer in `NutritionAgent.present()` receives structured outcome data but may not change status, score, safety findings, or recommendations. Post-process LLM content to append/enforce disclaimers on all outcomes, not just fallback paths.

---

## 8. Database Evolution Plan

### Existing tables

The current migration at `C:\dev\multi-agent-coach\app\db\migrations\004_create_nutrition_tables.sql` creates:

- `systemdb.nutrition_profiles`
- `systemdb.meal_logs`
- `systemdb.nutrition_assessments`
- `systemdb.food_cache`

### Forward migration requirements

First implement `C:\\dev\\multi-agent-coach\\app\\db\\migrate.py` with the exact Section 1.1 migration-ledger/bootstrap protocol and replace legacy `database.py:run_migrations()` startup ownership before adding nontrivial migration files. Its `run_migrations(check_only=False)` and shared `validate_compatible_schema()` interface are consumed by the one-shot CLI and all service readiness paths. The authoritative ledger is schema-qualified as `systemdb.schema_migrations`; it uses one session-scoped advisory lock held for the complete run, raw-file SHA-256 checksums, atomic per-migration-plus-ledger writes, verified legacy baselining of immutable `000`–`005`, and fatal mismatch handling. Validate clean install, legacy baseline/upgrade, historical-checksum failure, and concurrent-runner serialization.

After that, create migration `006` (and later forward-only migrations). It must contain only forward-compatible additions required by this plan:

- a nutrition-target table or target version fields for the approved explicit target-save behavior;
- indexes supporting `user_id`, date-range, and newest-first history queries;
- normalized cache freshness metadata for the Section 1.1 USDA refresh policy;
- structured safety/escalation fields for the required user-safe assessment projection and policy audit.

Do not modify migrations `004` or `005` if they may already have been applied. Remove duplicate table creation from `NutritionRepository.ensure_schema()` and `RecoveryRepository.ensure_schema()` after the migration ledger is in place; service startup/readiness must validate schema compatibility rather than mutate it. This is the only Recovery touchpoint in scope and requires no Recovery feature work.

---

## 9. Production-Grade Hardening Additions

These items expand the implementation from feature-complete to production-grade. They are required unless explicitly deferred with a recorded decision.

### 9.1 Rate limiting and abuse controls

- [ ] Implement the selected Section 1.1 Redis-backed limiter and its per-user/per-route limits on public `/api/nutrition/*` routes. Verify the fixed keys, `429` envelope, and `Retry-After` behavior.
- [ ] Use the selected shared Redis backend for production rate limits; in-memory rate limiting is allowed only for local development and tests.

- [ ] Add Nutrition Agent internal-service throttling at `300/min` per caller service identity, enforced after token validation with Redis in production. The main API is the only permitted caller identity in this release; failures return internal `429` without secrets or upstream details.
- [ ] Add USDA usage controls: cache-first lookup, the Section 1.1 minute/hour/day per-instance caps, timeout handling, failure backoff, and the specified per-process circuit breaker when the USDA dependency is degraded.
- [ ] Add optional LLM usage controls if `NUTRITION_LLM_ENABLED=true`: `NUTRITION_LLM_REQUESTS_PER_USER_PER_DAY=20`, `NUTRITION_LLM_MAX_COST_USD_PER_DAY=25`, and `NUTRITION_LLM_ENABLED=false` as the immediate kill switch. Enforce user quota in Redis in production, stop LLM requests when either ceiling is reached, use deterministic presentation instead, and emit only bounded/redacted cost/error metrics.
- [ ] Document exact rate-limit status codes, response body shape, retry headers, and user-facing fallback behavior.

### 9.2 History and adherence semantics

- [ ] Replace per-meal averages with daily aggregation for nutrition history.
- [ ] Define and implement the history window contract, including `window_days`, `days_with_logs`, `meal_logs`, `average_daily_calories`, `average_daily_protein_g`, `average_daily_carbs_g`, and `average_daily_fat_g`.
- [ ] Implement the Section 1.1 calorie-adherence formula and null/evidence behavior. Do not add macro adherence until persisted macro targets and a reviewed formula are approved.
- [ ] Return only `calorie_adherence_percentage` for this release. Defer `protein_adherence_percentage` and `macro_adherence_percentage` until persisted macro-target semantics and reviewed formulas are approved in a dated Section 14 decision.
- [ ] Add tests proving daily aggregation is correct when users log multiple meals per day and when some days have no logs.

### 9.3 Meal-log management and deferred idempotency

- [ ] Add public and internal support for listing meal logs with date-range filters, Section 1.1 offset pagination only, newest-first sorting, and maximum date-range limits. Cursor pagination is explicitly deferred.
- [ ] Add public and internal support for retrieving, updating, and deleting a single meal log by ID, with user ownership enforced at both the main API and Nutrition Agent layers.
- [ ] Before production readiness, make an explicit API-level idempotency decision. If approved, define the versioned API header/request and replay/conflict response contract, add a forward-only migration for key persistence and uniqueness, define key retention/expiry, and add concurrent-write and timeout-retry integration coverage. Until then, each valid create request remains a distinct meal-log record.

### 9.4 Assessment history

- [ ] Add public and internal assessment-history endpoints with pagination, date/status filters, and user ownership checks.
- [ ] Expose only approved user-safe assessment fields; do not expose raw prompts, internal service tokens, raw LLM context, or unnecessary tool internals.
- [ ] Apply this binding first-release assessment-history retention/deletion policy: retain only the `SAFETY-POLICY.md` approved sanitized assessment projection until the user account is deleted; users have no individual assessment-deletion endpoint in this release; account deletion hard-deletes associated nutrition assessments through the user foreign-key cascade; and administrator export, legal-hold, and retention-override workflows are out of scope. Any new retention period, individual deletion workflow, raw-data retention, or non-cascade deletion behavior requires an approved privacy-policy decision and forward migration before implementation.
- [ ] Add tests for assessment-history pagination, filtering, ownership isolation, and field redaction.

### 9.5 Food search and USDA resilience

- [ ] Add public and internal food-search endpoints with the canonical `API-CONTRACT.md` 1–100 character query validation, input normalization, and rate limiting.
- [ ] Implement cache-first behavior: local cache search first, USDA fallback only when configured and needed, normalized results, and controlled cache writes.
- [ ] Add source metadata to food results, such as `source`, `fdc_id`, `cache_hit`, and `last_updated` where applicable.
- [ ] Add negative caching or short-lived suppression for repeated no-result/high-failure lookups.
- [ ] Replace or augment broad `ILIKE '%query%'` search with a scalable strategy before growing the cache significantly, such as a normalized search column, PostgreSQL full-text search, or `pg_trgm` GIN indexes.
- [ ] Add tests for cache hit, cache miss, USDA success, USDA timeout, USDA failure, no-key cache-only mode, and malformed external data.

### 9.6 Nutrition service client resilience

- [ ] Replace one-off `httpx.post()` calls with the lifecycle-managed reusable async client defined solely by `API-CONTRACT.md`, including its connection pooling, separate connect/read/write/pool/total timeouts, read-only retry, and circuit-breaker policy.
- [ ] Use async client methods for public FastAPI routes so nutrition operations do not block the event loop; retain a clearly separated synchronous adapter only if the LangGraph worker requires it.
- [ ] Implement the `OPERATIONS.md` fallback boundary exactly: programmatic routes return the canonical dependency error without local mutation/fallback; only chat may use its local specialist fallback for the documented conditions.
- [ ] Map Nutrition Agent errors to stable public API errors without leaking internals.
- [ ] Propagate request/correlation IDs from the main API to the Nutrition Agent.

### 9.7 Observability

- [ ] Use current Python `logging` with module loggers, explicit redaction, and request-ID middleware/client propagation for both the main API nutrition path and Nutrition Agent endpoints.
- [ ] Redact sensitive fields in logs, including internal tokens, USDA/OpenAI keys, raw Authorization headers, raw meal descriptions, medical/nutrition-risk messages, and sensitive profile health details by default.
- [ ] Define OpenTelemetry-ready metric/span names and bounded attributes for request count, status class, endpoint latency, database latency, USDA cache-hit/failure/latency, LLM call/failure/latency/cost, safety escalation count, fallback count, and circuit-breaker state; keep exporters disabled by default unless configured.
- [ ] Enforce the Section 1.1 bounded-label allowlist; metrics must never include user IDs, request IDs, user content, health data, search queries, or raw exception strings as labels.
- [ ] Add centralized timing wrappers around main API route handling, nutrition client calls, Nutrition Agent route handling, database queries, USDA calls, and optional LLM calls so tracing can be enabled later without rewriting business logic.
- [ ] If metrics/exporters are enabled, add alert thresholds for elevated 5xx rate, p95 latency, database pool saturation, USDA failure rate, LLM failure/cost spike, and safety escalation anomalies.

### 9.8 Health, readiness, and dependency checks

- [ ] Implement the exact Section 1.1 unauthenticated `/health/live`, `/health/ready`, and deprecated `/health` alias contract on the Nutrition Agent, including non-sensitive `503` readiness checks.
- [ ] Apply the same liveness/readiness/compatibility-alias response contract to the main API. Main-API readiness checks required configuration, database connectivity, compatible migration ledger/schema, Redis in production, and a valid Nutrition Agent URL/rollout configuration when `USE_NUTRITION_AGENT_SERVICE=true`; it must not call the Nutrition Agent. Main-API liveness performs no dependency, migration, or configuration check.
- [ ] Implement the required/optional configuration validation from Section 1.1, including production rejection of placeholders/defaults and cache-only/deterministic-only optional modes.
- [ ] Configure Compose/deployment health checks to call `/health/ready`; do not use liveness as a dependency health signal.

### 9.9 Input validation and normalization

- [ ] Trim and normalize user-supplied strings, enums, dietary restrictions, allergies, meal descriptions, and food-search queries.
- [ ] Add maximum counts and item lengths for arrays such as allergies and dietary restrictions.
- [ ] Reject or sanitize control characters and clearly define markdown/HTML escaping behavior for user-provided descriptions displayed later.
- [ ] Validate plausible macro/calorie consistency when both calories and macros are provided; reject or flag implausible logs according to a documented rule.
- [ ] Add upper bounds for macros and calories in schemas and database constraints to prevent unrealistic values and storage abuse.

### 9.10 Safety policy versioning and governance

- [ ] Add `policy_version` or `ruleset_version` to nutrition assessment responses and persisted assessment rows.
- [ ] Record the deterministic safety policy version used for every assessment so future changes are auditable.
- [ ] Add a changelog process for safety threshold, escalation, disclaimer, and target-generation changes.
- [ ] Keep regression tests pinned to expected behavior for each supported policy version where practical.

### 9.11 LLM safety hardening

- [ ] Ensure the LLM presentation layer cannot alter `status`, `score`, structured recommendations, `tool_trace`, TDEE, macro targets, or safety escalation decisions.
- [ ] Validate generated output length, required disclaimer text, escalation wording, and absence of forbidden content before returning it.
- [ ] For `status=escalate`, always return deterministic-only safety text; do not call the LLM presentation layer.
- [ ] Add prompt-injection tests where user text asks to ignore safety instructions, reveal prompts/secrets, modify status, or omit disclaimers.
- [ ] Add fallback to deterministic response whenever validation fails.

### 9.12 Expanded nutrition safety scope

- [x] Implement the binding deterministic safety matrix in `docs\\nutrition_agent\\SAFETY-POLICY.md`; it is the sole source for trigger names/order, structured and phrase-derived signals, score, referral text, user-safe projections, and persistence boundaries. Do not duplicate, rename, or supplement policy trigger codes in this plan. Every escalation returns `status=escalate`, `score=10`, ordered `safety_findings`, and the exact policy referral text; no LLM call. Target calculation/save and meal-plan generation return `422 NUTRITION_SAFETY_REFERRAL_REQUIRED`; assessment/chat returns only the escalation projection. Required fixtures are the policy's regression-test matrix, including every structured value, each bounded phrase family, deduplication/order, and non-retention of source text.

  - **2026-09-01 — Complete:** Evaluation treats deterministic escalation as terminal: it persists and returns the safe assessment without entering `NutritionAgent.present()`. Regression coverage now exhausts structured values, bounded phrase families, stable policy ordering/deduplication, urgent projection, target calculation/save and meal-plan referrals for every escalation code, and raw-context/source-text non-retention in response and persistence projections.

- [x] Normalize only the Section 1.1 structured fields and bounded case-insensitive phrase sets for this release; do not infer diagnoses from unrelated prose. Verify unknown enums fail `422`, duplicate valid conditions collapse into policy-defined order, `unknown` does not suppress a message signal, and raw safety context is absent from persistence/logs/responses/telemetry. Any matrix change requires a safety-owner approval, policy-version bump, changelog entry, and regression-test update.
- [x] Ensure target calculation and meal planning refuse unsafe recommendations for every matrix match and that food-allergy filtering still applies when no escalation trigger is present.
- [x] Add tests proving medical/nutrition-risk messages do not produce prescriptive meal plans, calorie deficits, or supplement advice.

### 9.13 Performance and load targets

- [ ] Meet these initial rollout SLOs: cached food search p95 `<200ms`; profile/history/meal-log p95 `<150ms`; deterministic evaluation p95 `<300ms`; USDA-backed search p95 `<2s` with the Section 1.1 timeout/fallback. Measure at 50 concurrent authenticated users for 15 minutes with error rate `<1%` excluding deliberately injected dependency failures.
- [ ] Load test cached food search, meal-log writes, daily-history aggregation, assessment writes, and deterministic evaluation.
- [ ] Test behavior under USDA timeout/failure, optional LLM timeout/failure, database latency, and database pool saturation.
- [ ] Validate database indexes against representative data sizes, including a larger food cache if production growth is expected.
- [ ] Deploy with 2 application workers per service instance, Nutrition Agent database pool `min_size=1`/`max_size=5` per worker, and a tested 50 concurrent-request per-instance assumption; document any capacity change in Section 14 with new load evidence.

### 9.14 Concurrency and race-condition coverage

- [ ] Test concurrent profile updates and define last-write-wins or conflict behavior.
- [ ] Test concurrent meal-log creation with and without idempotency keys.
- [ ] Test concurrent food-cache writes after USDA lookups and ensure duplicate cache rows are avoided.
- [ ] Test concurrent assessment writes and pagination consistency.
- [ ] Test graceful failure when the database pool is exhausted or downstream dependencies stall.
### 9.15 Documentation consistency blocker

- [x] Supersede `C:\\dev\\multi-agent-coach\\services\\nutrition_agent\\IMPLEMENTATION_SUMMARY.md`; remove or qualify “ready for deployment” and “implementation complete” claims until this plan's production checklist passes.
  - **2026-08-30:** Replaced completion claims with a scaffold inventory, explicit non-compliance boundaries, the narrow rollout-test baseline, and links to canonical implementation contracts. Verified with repository text search and `git diff --check`.
- [x] Correct `C:\\dev\\multi-agent-coach\\services\\nutrition_agent\\README.md` where it describes currently unwired utilities as complete endpoint behavior.
  - **2026-08-30:** Replaced legacy endpoint/deployment instructions with canonical architecture, migration, health, test-isolation, privacy, and configuration guidance. Verified with repository text search and `git diff --check`.
- [x] Ensure all docs consistently state which routes are public through the main API and which routes remain private internal Nutrition Agent routes.
  - **2026-09-03:** Aligned the main README, API reference, service README, and canonical contract: JWT-authenticated `/api/nutrition/*` is the public programmatic boundary; token-protected `/v1/nutrition/*` is private-only; `/api/chat` remains the intended user-facing nutrition interaction.

## 10. Test and Acceptance Checklist

### Unit tests

- [ ] Add `C:\dev\multi-agent-coach\tests\test_nutrition_assessment.py`, modeled after `test_recovery_assessment.py`.
- [ ] Test medical-risk phrases yield `escalate` with no prescriptive nutrition advice.
- [ ] Test eating-disorder signals yield `escalate` and required warning content.
- [ ] Test calorie, BMI, meal-frequency, logging-consistency, and adherence scoring boundaries.
- [ ] Test prompt-injection text cannot alter deterministic assessment.
- [ ] Add `C:\dev\multi-agent-coach\tests\test_nutrition_tools.py` for exact BMR/TDEE values, macro calculation guardrails, and meal allergy/restriction filtering.
- [ ] Test `NutritionAgent.present` under disabled LLM, missing key, successful response, malformed response, and exception paths.

### Repository, client, and route tests

- [ ] Add repository tests for profile, meal-log, daily-history, target, food-cache, and assessment-history queries using an isolated database.
- [ ] Add `C:\dev\multi-agent-coach\tests\test_nutrition_agent_client.py` with mocked internal HTTP responses and failure modes.
- [ ] Add `C:\dev\multi-agent-coach\tests\test_nutrition_routes.py` for JWT requirements, schema validation, user-ID derivation, and cross-user denial.
- [ ] Test cache-first food search, USDA success, USDA failure, and no-key behavior without a live external dependency.

### CI, migration, secret-scan, and load evidence

- [ ] Extend `.github/workflows/ci.yml` with a PostgreSQL 16 service named `nutrition-test`, configure `NUTRITION_TEST_DATABASE_URL` to database `nutrition_test`, and run the isolated fixture/migration suite with `DATABASE_URL` set to a distinct non-test database name so fixture guard tests are meaningful.
- [ ] Run `uv run pytest -q` for the complete test suite and a dedicated migration command/test target covering clean install, legacy `000`–`005` baseline/upgrade, checksum mismatch, rerun, and advisory-lock concurrency against separate disposable databases.
- [ ] Add a tracked-secret scan CI step using `gitleaks` with no broad allowlist for the exposed USDA credential. The credential-owner rotation/revocation attestation remains a release gate even after a scan passes.
- [ ] Add a reproducible load script under `tests/load/` using an already-approved project dependency or a documented CI-installed tool. It authenticates 50 fixture users, runs for 15 minutes, writes machine-readable latency/error results, and calculates p95 from successful non-injected requests. CI may run a short smoke profile; the full 15-minute profile is mandatory for staging and every rollout step.
- [ ] Extend the dedicated migration target with legacy-manifest failures for missing required objects/indexes, altered canonical food-cache values, incorrect 220-row count, and partial ledger; prove it aborts before ledger mutation. Verify clean install performs only the `systemdb` bootstrap exception before immutable migrations.
- [ ] Add a Compose smoke command that starts the database, executes `python -m app.db.migrate`, starts Nutrition Agent and main API, verifies private `/health/ready` and public main-API readiness, then tears down with volumes removed. Do not use service startup to execute migrations or modify other-agent startup behavior.
- [ ] Build the Nutrition Agent image in CI/Compose smoke to prove its Dockerfile references only tracked required sources.
- [ ] No type checker is currently configured. Do not claim type-check evidence until a tool and command are deliberately adopted and added to CI.

### End-to-end and operations tests

- [ ] Start the Nutrition-only Compose path using the explicit migration-job ordering and verify main API plus Nutrition Agent `/health/live`, `/health/ready`, and the required deprecated `GET /health` liveness aliases. This plan does not require changes to or validation of other-agent services.
- [ ] Verify main API nutrition operations work with `USE_NUTRITION_AGENT_SERVICE=true`, the configured nutrition-only internal token, and sticky rollout assignment at `0`, `10`, `50`, and `100` percent.
- [ ] Verify a nutrition-service timeout/5xx follows the documented safe fallback behavior in chat.
- [ ] Verify public API cannot access the nutrition microservice directly or use another user's ID.
- [ ] Verify no real service token or USDA key is present in tracked configuration/docs.
- [ ] Run ownership, rate-limit, idempotency, pagination, and public/internal boundary tests for the public nutrition API.
- [ ] Run resilience tests for Nutrition Agent timeout/5xx, USDA timeout/failure/no-key behavior, and optional LLM failure/validation fallback.
- [ ] Run observability checks proving request IDs propagate and sensitive fields, including request-scoped safety context, are redacted from logs.
- [ ] Run observability checks proving metric labels remain within the Section 1.1 allowlist and `/metrics` is private-only.
- [ ] Run concurrency tests for profile updates, meal-log idempotency, food-cache writes, and assessment writes.
- [ ] Run load/performance tests against the defined p95 latency and dependency-failure targets.
- [ ] Run `uv run pytest -q` successfully, plus the dedicated migration, Compose smoke, secret-scan, and required staging load commands specified above.
- [ ] Run the project formatter/linter and record exact command/results. No type-check result is required until a type checker is adopted and configured in CI.

---

## 11. Rollout and Operational Plan

1. **Release-blocker evidence:** attach the required product, privacy, and safety-owner approvals; USDA rotation/revocation attestation; and passing CI secret-scan result. These must precede user-facing enablement and cannot be self-certified by implementation authors.
2. **Database gate:** run the Section 1.1 clean-install bootstrap, verified legacy-manifest baseline/upgrade, checksum-mismatch, manifest-object/food-cache failure, and concurrent-migration tests against staging. Back up staging before the forward migration and abort on any ledger/schema incompatibility.
3. **Deployment gate:** build the validated Nutrition image, run the one-shot migration command before service rollout, and deploy Nutrition Agent with non-default secrets from secret management, private-only network access, Redis, and `/health/ready` health checking. Deploy the main API with internal service DNS, verified private metrics access, and leave `USE_NUTRITION_AGENT_SERVICE=false` until all smoke and observability checks pass. This gate does not alter other agents.
4. **Pre-traffic validation:** execute the Section 10 acceptance crosswalk, including authenticated ownership, idempotency, readiness failure, cache-only/no-key, dependency timeout, deterministic escalation, redaction, and 50-concurrent-user load tests. Record command, environment, commit, and result in Section 14.
5. **Controlled enablement:** enable `USE_NUTRITION_AGENT_SERVICE=true` for staging, then production with `NUTRITION_AGENT_ROLLOUT_PERCENT=10`, `50`, and `100`. Assignment uses the Section 1.1 sticky authenticated-user hash; do not use an ad hoc cohort selector. Hold each step for at least 30 minutes; advance only if error rate is below 1%, listed p95 SLOs pass, no unexpected safety escalation anomaly occurs, and no credential/redaction alert fires.
6. **Operational monitoring:** monitor error rate, latency, fallback count, rate-limit count, safety escalation count, USDA cache-hit/failure/latency, optional LLM cost/failure/latency, database pool saturation, and circuit-breaker state. Alert at 2% 5xx for 5 minutes, 10% dependency failures for 5 minutes, or any confirmed secret-log event; pause rollout and investigate.
7. **Rollback:** immediately disable `USE_NUTRITION_AGENT_SERVICE` on a breached gate; retain the existing local specialist fallback. Do not roll back an applied forward migration by editing history—ship a compensating migration after data impact review.

### Requirements-to-acceptance-test crosswalk

| Requirement | Required automated evidence | Rollout gate |
|---|---|---|
| Authentication and ownership | Route tests for missing/invalid JWT, public `user_id` rejection, and cross-user read/update/delete denial | Pre-traffic validation |
| Health and configuration | Main API and Nutrition Agent liveness isolation, readiness success/each `503` cause, deprecated aliases, rollout-config validation, and production-placeholder tests | Deployment gate |
| Migration safety | Clean-install `systemdb` bootstrap/upgrade, exact legacy `000`–`005` manifest baseline then `006+`, checksum mismatch, manifest object/food-cache mismatch, rerun, and advisory-lock concurrency tests | Database gate |
| Privacy, secret safety, and external governance | Redaction capture tests, tracked-secret scan, USDA rotation attestation, and owner approvals | Release-blocker evidence |
| Input, pagination, and idempotency | Boundary/normalization tests, 31-day range tests, pagination total/order tests, identical/changed replay and concurrent create tests | Pre-traffic validation |
| Safety and presentation | Policy-version regression tests for every Section 9.12 matrix row; structured-context enum/normalization/privacy tests; escalation/refusal tests; LLM injection/validation/fallback tests | Pre-traffic validation |
| Food resilience | Cache hit/miss, stale fallback, no-key, suppression, quota, malformed USDA data, and timeout tests | Pre-traffic validation |
| Service resilience and observability | Mocked retry/breaker/fallback tests; rollout-boundary tests; request-ID, bounded-label metrics, trace, redaction, and private-metrics-access integration tests | Pre-traffic validation |
| Performance | 50-concurrent-user, 15-minute load run meeting the Section 9.13 SLO/error thresholds | Each controlled enablement step |

---

## 12. Documentation Updates Required

- Create nutrition-specific documentation under `C:\dev\multi-agent-coach\docs\nutrition_agent\`. Recommended files are `API-CONTRACT.md`, `SAFETY-POLICY.md`, `MIGRATION-RUNNER.md`, `OPERATIONS.md`, `TESTING.md`, and `ROLLOUT.md`.
- `C:\dev\multi-agent-coach\docs\nutrition_agent\API-CONTRACT.md`: Document chat/orchestrator-first user interaction, optional public `/api/nutrition/*` programmatic routes if implemented, internal `/v1/nutrition/*` routes, JWT/service-token requirements, request/response examples, and endpoint status behavior.
- `C:\dev\multi-agent-coach\docs\nutrition_agent\SAFETY-POLICY.md`: Document `nutrition-safety-v1`, escalation/referral triggers, target/meal-plan refusal behavior, disclaimer rules, allowed safety-context enum values, and privacy/persistence restrictions.
- `C:\dev\multi-agent-coach\docs\nutrition_agent\MIGRATION-RUNNER.md`: Document the one-shot migration CLI/job, ledger format, legacy bootstrap, advisory lock, clean-install/upgrade behavior, and failure handling.
- `C:\dev\multi-agent-coach\docs\nutrition_agent\OPERATIONS.md`: Document configuration, secrets, current logging behavior, OpenTelemetry-ready optional settings, rate limits, readiness/liveness, private metrics access, USDA fallback behavior, and operational rollback.
- `C:\dev\multi-agent-coach\docs\nutrition_agent\TESTING.md`: Document nutrition test structure, isolated PostgreSQL fixture strategy, mocked USDA/OpenAI behavior, CI commands, Compose smoke tests, secret-scan command, and load/performance evidence.
- `C:\dev\multi-agent-coach\docs\nutrition_agent\ROLLOUT.md`: Document orchestrator/chat rollout bucketing, staged enablement, disable/rollback procedure, and validation evidence required before increasing traffic.
- `C:\dev\multi-agent-coach\docs\API-REFERENCE.md`: Link to `docs/nutrition_agent/API-CONTRACT.md` and summarize only shipped public API behavior; do not duplicate the detailed nutrition contract.
- `C:\dev\multi-agent-coach\README.md`: Add high-level setup and service enablement information, pointing detailed nutrition instructions to `docs/nutrition_agent`.
- `C:\dev\multi-agent-coach\services\nutrition_agent\README.md`: Correct claims that currently describe unwired utilities as complete endpoint behavior; link to the new `docs/nutrition_agent` documents for authoritative contracts and operations.
- `C:\dev\multi-agent-coach\.env.example`: Add safe placeholders for `USE_NUTRITION_AGENT_SERVICE`, `NUTRITION_AGENT_ROLLOUT_PERCENT`, `NUTRITION_AGENT_URL`, `NUTRITION_INTERNAL_SERVICE_TOKEN`, `NUTRITION_LLM_ENABLED`, `USDA_FDC_API_KEY`, and optional `OTEL_*` settings; do not alter other-agent token conventions in this nutrition change.
- `C:\dev\multi-agent-coach\docker-compose.yml`: Keep nutrition tokens/key values environment-derived, use `NUTRITION_INTERNAL_SERVICE_TOKEN` consistently across the main API and Nutrition Agent, add an explicit one-shot migration job before either service, keep Nutrition Agent private, and do not change other-agent configuration as part of this plan.
- `C:\dev\multi-agent-coach\services\nutrition_agent\Dockerfile`: Remove the missing `data` build-context copy or deliberately add/document its tracked source, then validate an image build before rollout.
- `C:\dev\multi-agent-coach\services\nutrition_agent\IMPLEMENTATION_SUMMARY.md`: Supersede or correct completion/deployment-ready claims until the production checklist passes.

---

## 13. Definition of Done

The nutrition-management implementation is complete only when all conditions below are met:

### Completion categories

Required for implementation-complete:

- Phase 0 migration/safety/credential gates are resolved or explicitly deferred.
- Orchestrator/chat path can route to the Nutrition Agent service safely.
- Internal Nutrition Agent routes required by implemented capabilities are complete.
- Programmatic main-API nutrition routes are complete for backend/test/future-UI capability.
- Deterministic assessment, target calculation, daily history/adherence, food cache, and meal-plan behavior are tested.
- Current Python logging, redaction, and request-ID propagation are implemented.

Required for user-facing release:

- USDA credential-governance evidence and secret scan pass.
- Migration ledger validates clean install and legacy upgrade.
- Safety policy tests pass.
- Rollout/rollback controls are documented.
- Required docs under `docs/nutrition_agent` are complete.

Optional/future unless explicitly enabled:

- Dedicated nutrition frontend UI.
- OpenTelemetry exporters.
- Public metrics endpoint.
- Repository-history rewrite if credential owner accepts rotation-only mitigation.

- [ ] The authenticated orchestrator/chat endpoint provides the required user-facing nutrition experience, and documented main-API nutrition routes provide ownership-safe programmatic operations for profiles, meal logs, food search, targets, plans, history, and assessment history.
- [ ] Authenticated users can retrieve correct, daily-aggregated history and explicitly defined adherence behavior.
- [ ] TDEE, macro targets, and meal plans are available through typed contracts and obey safety/restriction rules.
- [ ] Food lookup is cache-first, rate-limited, resilient to USDA failure, observable, and does not use committed credentials.
- [ ] Deterministic safety escalation is policy-versioned, tested across expanded safety/referral triggers and structured safety-context validation/privacy behavior, and cannot be overwritten by the LLM presentation layer.
- [ ] Assessment history is user-scoped, paginated, filterable, retention-aware, and exposes only approved user-safe fields.
- [ ] Nutrition microservice communication is private, token-protected, configured consistently, resilient through pooled clients/timeouts/circuit breakers, and has known fallback behavior.
- [ ] Database changes are delivered by the authoritative one-shot migration job in forward-only migrations and verified for clean install and upgrade paths; services only validate compatibility.
- [-] Unit, repository, client, route, integration, concurrency, resilience, observability, and load/performance tests pass.
  - **2026-08-31:** Deferred for the development-core implementation pass by the Section 14 development-core scope decision. This is not acceptance evidence and must be restored to required work before pre-production or user-facing enablement.
- [ ] API/deployment documentation accurately matches the shipped behavior.
- [ ] Every required item in the Master Checklist and Sections 9 and 10 is `[x]` or has an explicit accepted `[-]` decision.

---

## 14. Decision and Progress Log

Add dated entries here when work is resumed or significant scope decisions are made.

- **2026-08-31 — Development-core implementation scope authorized:** Implement the Nutrition Agent's end-to-end local/dev core functions only: canonical typed schemas; deterministic `nutrition-safety-v1` enforcement and privacy-safe projections; migration-owned persistence and validation-only startup; profiles; meal logs; target calculation/versioned save; daily history/adherence; restriction-safe meal planning; normalized cache-first food lookup with development cache-only/no-key behavior; canonical private routes; authenticated public programmatic routes; private client methods; and orchestrator/chat integration. The legacy Nutrition scaffold may be rewritten as needed and remains non-authoritative until it conforms to these contracts. **Deferred:** new/expanded automated tests, test fixtures and isolated test-database work, CI, secret scanning, Redis/rate-limit infrastructure, Compose/deployment work, pre-production/staging, production credential governance, observability rollout, load testing, and rollout/rollback execution. These deferrals do not relax API compatibility, deterministic safety, privacy-safe persistence, authenticated ownership, migration-ledger ownership, or validation-only startup. Deferred checklist work must not be marked complete and remains mandatory before user-facing enablement.

- **2026-08-30 — Nutrition scaffold inventory and disposition:** Inspected every Nutrition-related uncommitted scaffold file before implementation. **Retain:** `.env.example` nutrition-safe placeholders; `app/config.py` nutrition service flags/token naming; `app/services/nutrition_rollout.py` and `tests/nutrition/test_rollout.py` sticky rollout utility/tests; `app/db/migrations/004_create_nutrition_tables.sql`, `005_seed_food_cache.sql`, and `legacy_000_005_manifest.json` as immutable historical facts; canonical `docs/nutrition_agent/*` contracts. **Rewrite:** `app/db/database.py` and `app/db/seed.py` startup ownership; `services/nutrition_agent/app/{main,repository,schemas,assessment,agent,tools,config}.py`; `app/services/{agent_service,nutrition_agent_client}.py`; `docker-compose.yml`; `services/nutrition_agent/{README.md,IMPLEMENTATION_SUMMARY.md,Dockerfile}`; `.github/workflows/ci.yml`; and nutrition integration tests, because they must conform to the canonical migration, safety, API, and operational contracts. **Revert:** none—no uncommitted Nutrition change is deleted without a contract-compliant replacement. This inventory does not certify the retained items as feature-complete.

- **2026-08-29 — Plan created:** Existing nutrition microservice scaffolding was inventoried. No implementation code was changed as part of planning. The first required implementation work is Phase 0 baseline/decisions, followed by the authenticated main-API nutrition router.
- **2026-08-29 — Production-hardening additions accepted:** Added required plan items for rate limiting, daily history/adherence semantics, meal-log CRUD/idempotency, assessment history, food search/USDA resilience, client resilience, observability, readiness/liveness, validation/normalization, safety policy versioning, LLM safety hardening, expanded nutrition safety scope, performance/load targets, concurrency testing, and documentation consistency.
- **2026-08-29 — Implementation-readiness decisions added:** Added binding nutrition-only token naming, public API and error conventions, idempotency/retention/concurrency defaults, target and adherence semantics, migration-ledger requirements, credential rotation, operational-stack selection, endpoint-contract, and isolated-test-environment gates. These are planning decisions only; all implementation checklist items remain pending until validated.
- **2026-08-29 — Execution contracts made explicit:** Added fixed health/readiness behavior, required versus optional configuration, numeric rate/payload/cache/client/load defaults, concrete operational package choices, isolated PostgreSQL fixture lifecycle, schema-qualified checksum-ledger bootstrap for immutable `000`–`005`, acceptance-test crosswalk, and evidence-based approval/credential rollout blockers. The USDA secret remediation and owner approvals remain externally blocked until their required evidence is recorded.
- **2026-08-29 — Implementation-readiness gaps resolved:** Defined `nutrition_test` database / `systemdb` schema isolation, an authoritative pre-service migration CLI/job, main-API and Nutrition-Agent health scope, hash-sticky authenticated-user rollout configuration, deterministic escalation/refusal matrix, exact schema-documentation requirement, bounded operational controls, and reproducible CI/Compose/load/secret-scan evidence. The USDA credential remains an external credential-owner remediation and history-governance gate; no credential or runtime configuration file was changed by this plan revision.
- **2026-08-30 — Readiness review corrections accepted:** Pinned rollout bucketing to SHA-256 of the decimal authenticated user ID. Clarified that the one-shot migration job exclusively owns the shared `systemdb` schema, requiring both Nutrition and Recovery runtime DDL to become compatibility validation; database provisioning remains infrastructure-owned. Main-API startup no longer performs migrations or seeding, and admin seeding is an explicit post-migration one-shot job. Deferred protein/macro adherence fields until macro-target semantics and formulas receive explicit approval.
- **2026-08-30 — Migration-lock implementation correction:** The runner must hold one session-scoped PostgreSQL advisory lock for the complete migration run. This preserves the required serialization while allowing each migration and its ledger entry to remain an independently atomic transaction; a transaction-scoped lock would be released after each migration commit.
- **2026-08-30 — Migration, testing, operations, and rollout contracts published:** Completed `docs/nutrition_agent/MIGRATION-RUNNER.md`, `TESTING.md`, `OPERATIONS.md`, and `ROLLOUT.md` with authoritative Phase 0 implementation contracts. Readiness Packs A-D are now documented; implementation and external approval/credential gates remain pending.


- **2026-08-30 — Development-first mode enabled:** Deferred production-only governance, credential-attestation, Redis/telemetry, and CI PostgreSQL gates while preserving them as production-release blockers. Added development rollout configuration and deterministic rollout tests so full Nutrition Agent development can proceed locally.

- **2026-08-30 — Flexible implementation-readiness defaults added:** Added recommended flexible defaults for Phase 0 evidence, schema contracts, database/migration design, route scope, rollout/configuration, safety policy, target calculations, meal plans, food cache/USDA behavior, testing, current-logging/OpenTelemetry-ready observability, health/readiness, orchestrator-first user interaction, deployment, and `docs/nutrition_agent` documentation ownership. The public error-code catalog was intentionally excluded per review direction.
- **2026-08-30 — Conflict-resolution defaults consolidated:** Reconciled readiness status, orchestrator-first user interaction, programmatic public-route scope, current-logging/OpenTelemetry-ready observability, health endpoint paths, USDA cache/circuit-breaker constants, structured safety context, policy-code naming, completion categories, and docs ownership into the authoritative sections.
- **2026-08-30 — API contract published:** Completed `docs/nutrition_agent/API-CONTRACT.md` as the canonical public/private route and schema contract for implementation. Section 7.1 now delegates to the canonical contract to avoid duplicate route tables.
- **2026-08-30 — Safety policy contract published:** Completed `docs/nutrition_agent/SAFETY-POLICY.md` with `nutrition-safety-v1`, structured safety context, stable trigger-code order, deterministic escalation behavior, LLM presentation safeguards, privacy-safe persistence rules, and a regression-test matrix.



- **2026-08-30 — Phase 0 docs and config hygiene started:** Created `docs/nutrition_agent/` skeleton docs and changed active Nutrition Agent configuration/client/Compose examples to use `NUTRITION_INTERNAL_SERVICE_TOKEN`. Removed the committed USDA key value from active tracked config and Compose defaults. The USDA credential-owner revocation/rotation attestation and CI secret-scan gate remain open and must not be self-certified.
- **2026-08-30 — Documentation contract corrections accepted:** Made `API-CONTRACT.md` the sole client-resilience authority and `OPERATIONS.md` the fallback-boundary authority; aligned food-search public validation to canonical normalized `q` length `1–100` while retaining cache/quota controls here as operational policy; and adopted the first-release sanitized assessment-history retention/deletion policy.
- **2026-08-30 — Development-first readiness reconciliation:** Recorded the passing rollout-test baseline and classified the existing Nutrition service as replaceable scaffolding rather than a compliant release surface. Made `SAFETY-POLICY.md` the sole trigger-code authority, removed the conflicting duplicate safety matrix, and separated local implementation prerequisites from production-only evidence. The migration runner and canonical route/safety implementations remain open Phase 0 work.
- **2026-08-30 — Documentation readiness corrections:** Established the canonical four-column migration ledger and narrowly permitted only the migration runner's clean-install `CREATE SCHEMA IF NOT EXISTS systemdb` bootstrap before ledger creation; database/role provisioning and all other out-of-migration DDL remain prohibited. Expanded the API contract with exact public/private paths and concrete profile, meal, target, food, safety, assessment, history, and meal-plan schemas. Added canonical `422 NUTRITION_VALUE_INCONSISTENT` and aligned its 20% tolerance, profile last-write-wins behavior, meal `PUT`, and payload bounds with Section 1.1. Added open Phase 0 tasks for scaffold disposition, dependency/CI wiring, and isolated `NUTRITION_TEST_DATABASE_URL` fixtures.
- **2026-09-01 � Immutable same-day target revisions aligned:** Updated daily-history target resolution to select `effective_from DESC, version DESC`, matching current-target lookup. The highest immutable same-day revision is therefore authoritative for both current and historical projections. Apply `008_nutrition_target_revisions.sql` before deploying the repository change; PostgreSQL integration remains skipped until `NUTRITION_TEST_DATABASE_URL` is configured.
- **2026-09-01 � Pooled client ownership boundary centralized:** Added ownership-scoped and shared-food methods to `NutritionAgentClient`. Authenticated public routes now derive the ID solely from `get_current_user` and delegate private user-path construction to that client, rather than constructing `/v1/nutrition/users/{id}` paths in route handlers.
- **2026-09-01 — Private-client resilience implemented:** `NutritionAgentClient` now uses the canonical 2s/5s/5s/2s/10s pooled-client timeouts, retries idempotent reads exactly once after qualifying connect/read timeouts or 502/503/504 responses with full jitter, never retries mutations, and opens a 30-second circuit after five qualifying failures in 30 seconds with one half-open probe. Mocked transport coverage proves response and timeout retry behavior, mutation non-retry, circuit opening, and probe reset. Validated with `uv run pytest -q tests/nutrition` (`156 passed, 1 skipped`), Ruff, compilation, and `git diff --check`; the PostgreSQL cache integration test remains skipped until `NUTRITION_TEST_DATABASE_URL` is configured.

- **2026-09-01 — Public Nutrition request boundary hardened:** Replaced unrestricted public mutation bodies with strict Pydantic request models reused from the private canonical profile, meal-log, target, and meal-plan schemas; routes forward validated JSON with model_dump(mode="json"). Canonical public error mapping now preserves recognized resource-not-found, safety-referral, and value-inconsistency codes without exposing private details. Boundary regressions prove invalid meal bodies fail before private-client invocation, request IDs remain in validation envelopes, and recognized downstream 404/422 codes retain their canonical envelopes. Validated with focused tests (14 passed), uv run pytest -q tests/nutrition (159 passed, 1 skipped), compilation, git diff --check, and Ruff with pre-existing FastAPI Depends(...) rule B008 excluded; PostgreSQL integration remains skipped until NUTRITION_TEST_DATABASE_URL is configured.

- **2026-09-03 — Local migration validation blocked safely:** `uv run python -m app.db.migrate --check` against the configured local `systemdb` reported `Not all migrations are applied`. The target is localhost/development but was not independently established as disposable, so no migration command was run and neither application process was started for live readiness probing. Focused main-API Nutrition tests passed (`188 passed, 1 skipped`) and Nutrition Agent tests passed (`6 passed`). Apply and validate the ledger only after configuring an explicitly disposable database, then run the documented readiness smoke.

- **2026-09-06 ? Development-core safety/profile evidence:** Aligned macro-target `other` calorie floor with canonical `nutrition-safety-v1` at 1200 kcal/day (male remains 1500); added exact floor, BMI, and weekly-loss boundary regression tests. Chat now reads its authenticated user?s private Nutrition profile, allowlists and validates a transient `NutritionProfileUpsert` handoff before evaluation, and retains local fallback for missing/invalid profile and profile/evaluation dependency failure. Focused validation: `uv run pytest tests/nutrition/test_nutrition_safety_policy.py tests/nutrition/test_private_safety_wiring.py tests/nutrition/test_chat_nutrition_service.py tests/nutrition/test_nutrition_agent_client_operations.py -q` ? **141 passed**. Live USDA smoke evidence: `uv run pytest tests/nutrition/test_usda_live_smoke.py -q` ? **1 passed in 2.05s**.

- **2026-09-06 — Core-1 PostgreSQL migration acceptance completed:** Used the explicitly isolated `NUTRITION_TEST_DATABASE_URL` targeting disposable `nutrition_test` (with `DATABASE_URL` distinct except while the one-shot runner was deliberately pointed at that target). Acceptance reset only `nutrition_test.systemdb`. A clean install and rerun produced and retained ledger versions `000`–`009`; a manually prepared immutable `000`–`005` legacy baseline was ledger-baselined without historical replay and upgraded through `009`; an intentionally mismatched temporary historical manifest raised before `systemdb` was created; two concurrent runners completed with the complete unchanged ledger; and `validate_compatible_schema()` returned database, ledger, and schema `ok` without DDL. `uv run pytest tests/nutrition/test_food_cache_postgres_integration.py -q -rs` passed: **1 passed in 0.63s**.
