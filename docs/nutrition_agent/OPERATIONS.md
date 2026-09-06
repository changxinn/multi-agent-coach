# Nutrition Agent Operations

Status: Canonical Phase 0 operations contract for implementation.

## Configuration and health

Nutrition Agent readiness requires `DATABASE_URL`, `DATABASE_SCHEMA=systemdb`, and `NUTRITION_INTERNAL_SERVICE_TOKEN`. With `USE_NUTRITION_AGENT_SERVICE=true`, main-API readiness also requires `NUTRITION_AGENT_URL`, the token, and a `NUTRITION_AGENT_ROLLOUT_PERCENT` integer `0`–`100`. `USDA_FDC_API_KEY` is optional (absent means cache-only); `OPENAI_API_KEY` is required only with `NUTRITION_LLM_ENABLED=true`; telemetry is optional. Production rejects empty, placeholder, and known local-development values for required/enabled secrets.

- `GET /health/live` performs no dependency/configuration check and returns `200 {"status":"live"}`.
- `GET /health` is its deprecated compatibility alias.
- `GET /health/ready` validates configuration, `SELECT 1`, and migration ledger/schema compatibility. It returns `200 {"status":"ready","checks":{"configuration":"ok","database":"ok","schema":"ok"}}` only when all pass; otherwise it returns `503` with check names only.

The Nutrition Agent has no deployed public ingress. `/v1/nutrition/*` requires `X-Internal-Service-Token` over private networking. Compose/deployment health checks use `/health/ready`.

## Migration and startup

Provision database, run `uv run python -m app.db.migrate`, optionally run the distinct post-migration seed job, then start Nutrition Agent and main API. In the repository Compose deployment, the one-shot `migrations` service executes this command after PostgreSQL is healthy; `api` and `nutrition-agent` wait for its successful completion. Runtime services do not migrate, seed, or execute DDL; incompatible ledger/schema is a readiness failure.

## Resilience, fallback, and rollback

`API-CONTRACT.md` is authoritative for client resilience: `2s/5s/5s/2s/10s` connect/read/write/pool/total timeouts; one full-jitter read retry only; five qualifying failures in 30 seconds opens a 30-second circuit with one half-open probe. Programmatic routes return `503 DEPENDENCY_UNAVAILABLE` on service failure and never locally mutate/fall back. Only chat falls back to the local nutrition specialist for disabled service, rollout exclusion, timeout, or private-service 5xx.

Food search is cache-first. No key, outage, quota, timeout, or open USDA circuit serves valid cached/stale results where available with bounded metadata; raw upstream errors/payloads never leave the service.

Use module loggers, request-ID propagation, and redaction. Never log tokens, keys, raw disclosures, meal descriptions, food queries, raw USDA payloads, prompts, or sensitive exception text. Metrics/traces use only service, route template, status class, dependency, cache outcome, safety outcome, and fallback outcome labels.

Disable chat routing with `USE_NUTRITION_AGENT_SERVICE=false` or rollout `0`. Direct programmatic routes are disabled by the master switch and return documented `SERVICE_DISABLED`/dependency errors. Rollback never requires schema rollback. User-facing production enablement remains gated by the master plan.