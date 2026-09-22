# Nutrition Agent service

Private FastAPI microservice for nutrition calculations, food-data queries, meal planning, and nutrition context. The scaffold exposes authenticated status and health endpoints; the functional nutrition operations are described in `docs/NUTRITION-AGENT-IMPLEMENTATION-PLAN.md`.

## Required environment

```text
INTERNAL_SERVICE_TOKEN=local-dev-recovery-token
DATABASE_URL=postgresql://user:password@host:5432/systemdb
DATABASE_SCHEMA=systemdb
USDA_FDC_API_KEY=
```

## Run locally

```bash
INTERNAL_SERVICE_TOKEN=local-dev-recovery-token \
python -m uvicorn services.nutrition_agent.app.main:app --reload --port 8004
```

Health check: `GET http://localhost:8004/health`

Private Nutrition status check: `POST http://localhost:8004/v1/nutrition/status`
with `X-Internal-Service-Token` and an empty JSON body (`{}`).

## USDA meal-log catalogue

The meal log reads USDA choices from the Nutrition-owned `nutrition_food_cache` table;
opening the modal never calls USDA. The root application automatically applies
`app/db/migrations/010_seed_nutrition_foundation_food_cache.sql` at startup. That
idempotent migration seeds 95 USDA Foundation foods with complete per-100 g macros;
it requires neither a bundled JSON export nor a USDA API key.

The table itself remains owned by migration
`app/db/migrations/006_add_nutrition_food_data_and_adherence.sql`. The seed uses
`ON CONFLICT (provider, provider_food_id) DO NOTHING`, so it never overwrites a
locally curated or subsequently refreshed food record.