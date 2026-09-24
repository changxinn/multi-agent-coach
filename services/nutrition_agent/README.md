# Nutrition Agent service

Private FastAPI microservice for nutrition calculations, food-data queries, meal planning, and nutrition context. The scaffold exposes authenticated status and health endpoints; the functional nutrition operations are described in `docs/NUTRITION-AGENT-IMPLEMENTATION-PLAN.md`.

## Required environment

```text
INTERNAL_SERVICE_TOKEN=local-dev-recovery-token
DATABASE_URL=postgresql://nutrition_agent:password@host:5432/nutritiondb
RUN_MIGRATIONS=true
USDA_FDC_API_KEY=
```

## Run locally

```bash
python -m uvicorn services.nutrition_agent.app.main:app --reload --port 8004
```

The service always loads `services/nutrition_agent/.env`, regardless of the
directory from which Uvicorn is started. Set `RUN_MIGRATIONS=true` there for
local database initialization. For a Nutrition database on the same local
PostgreSQL server as the main app, use a separate database, for example
`postgresql://nutrition_agent:password@localhost:5432/nutritiondb`; do not use
the main application's `systemdb` database.

Health check: `GET http://localhost:8004/health`

Private Nutrition status check: `POST http://localhost:8004/v1/nutrition/status`
with `X-Internal-Service-Token` and an empty JSON body (`{}`).

## USDA meal-log catalogue

The meal log reads USDA choices from the Nutrition-owned `nutrition_food_cache` table;
opening the modal never calls USDA. When `RUN_MIGRATIONS=true`, the Nutrition Agent applies its own
`app/db/migrations/002_seed_nutrition_foundation_food_cache.sql` at startup. That
idempotent migration seeds 95 USDA Foundation foods with complete per-100 g macros;
it requires neither a bundled JSON export nor a USDA API key.

The table itself remains owned by the Nutrition Agent migration
`app/db/migrations/001_create_nutrition_schema.sql`. The seed uses
`ON CONFLICT (provider, provider_food_id) DO NOTHING`, so it never overwrites a
locally curated or subsequently refreshed food record.

Docker Compose sets `RUN_MIGRATIONS=true` for the Nutrition Agent container.
This keeps service unit tests independent of a live PostgreSQL instance. In a
production deployment, run the same migration step once as a dedicated job.