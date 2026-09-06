# Nutrition Agent Microservice

**Implementation status: development-core implementation.** This private
FastAPI service implements the current canonical Nutrition contracts for local
development. It is not a public API and is not production-ready: the release
gates in the master implementation plan, including migration upgrade evidence,
credential governance, rate limiting, observability, CI, and deployment
validation, remain outstanding.

## Architecture boundary

The main API owns authenticated public routes under `/api/nutrition` and derives `user_id` from the JWT. Nutrition Agent exposes only private, token-authenticated routes under `/v1/nutrition` over private networking. It must never be exposed directly to browsers or public ingress.

The implementation targets are defined in these authoritative documents:

- `C:\dev\multi-agent-coach\docs\nutrition_agent\NUTRITION-SERVICE-IMPLEMENTATION-PLAN.md`
- `C:\dev\multi-agent-coach\docs\nutrition_agent\API-CONTRACT.md`
- `C:\dev\multi-agent-coach\docs\nutrition_agent\SAFETY-POLICY.md`
- `C:\dev\multi-agent-coach\docs\nutrition_agent\MIGRATION-RUNNER.md`
- `C:\dev\multi-agent-coach\docs\nutrition_agent\OPERATIONS.md`
- `C:\dev\multi-agent-coach\docs\nutrition_agent\TESTING.md`

## Local development prerequisites

1. Provision a disposable PostgreSQL database. Database creation is infrastructure-owned.
2. Configure `DATABASE_URL`, `DATABASE_SCHEMA=systemdb`, and `NUTRITION_INTERNAL_SERVICE_TOKEN`. For main-API integration also configure `USE_NUTRITION_AGENT_SERVICE`, `NUTRITION_AGENT_URL`, and `NUTRITION_AGENT_ROLLOUT_PERCENT`.
3. Run the one-shot migration command from the repository root before starting either runtime service:

   ```powershell
   uv run python -m app.db.migrate
   ```

   Normal service startup must only validate schema compatibility; it must not provision a database, run migrations, seed data, or execute application DDL.
4. Start the service from this directory so its `app` package cannot resolve to the main API package:

   ```powershell
   Push-Location C:\dev\multi-agent-coach\services\nutrition_agent
   python -m uvicorn app.main:app --reload --port 8003
   Pop-Location
   ```

`USDA_FDC_API_KEY` is optional: no key means cache-only behavior. With a key, USDA records are fresh for 30 days and may be returned only as a stale fallback through 180 days. No-result and unavailable searches are query-suppressed for 15 minutes; each service instance caps USDA requests at 30/minute, 1,000/hour, and 10,000/day across search and detail calls. The corresponding `FOOD_CACHE_*` and `USDA_*` settings are validated and documented in `.env.example`. `OPENAI_API_KEY` is required only when the eventual `NUTRITION_LLM_ENABLED=true` path is implemented; keep that path disabled until the canonical safety and post-validation tests pass. Never commit keys or tokens.

## Health and private authentication contract

- `GET /health/live` is unauthenticated and returns `200 {"status":"live"}` without dependency checks. `GET /health` remains a compatibility alias.
- `GET /health/ready` validates configuration, database connectivity, and migration/schema compatibility. It returns `503` until all checks pass.
- Every `/v1/nutrition/*` route requires `X-Internal-Service-Token`, exactly matching `NUTRITION_INTERNAL_SERVICE_TOKEN`.

Canonical private paths, typed request/response shapes, ownership rules, and
error behavior are in `API-CONTRACT.md`. User-scoped private operations use
`/v1/nutrition/users/{user_id}/...`; shared food-reference operations use
`/v1/nutrition/foods...`. Neither path family is a public compatibility
surface. The main API alone exposes `/api/nutrition/*` after JWT
authentication and is responsible for deriving the user ID.

## Testing

Run service tests in a separate process from the service directory:

```powershell
Push-Location C:\dev\multi-agent-coach\services\nutrition_agent
python -m pytest tests -q
Pop-Location
```

Migration/repository tests require the disposable `nutrition_test` PostgreSQL database and must fail closed for any other target. The complete test matrix and commands are in `TESTING.md`.

## Safety and privacy

`SAFETY-POLICY.md` is the sole authority for safety trigger codes, thresholds, escalation messages, disclaimers, LLM bypassing, and allowed assessment-history fields. Never log or persist raw medical disclosures, food queries, meal descriptions, prompts, reasoning, or tool traces.