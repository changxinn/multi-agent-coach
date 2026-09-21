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
opening the modal never calls USDA. Import the approved Foundation, SR Legacy, and
Survey/FNDDS datasets after applying migrations:

```bash
cd multi-agent-coach
PYTHONPATH=multi-agent-coach/services/nutrition_agent \
  .venv/bin/python services/nutrition_agent/import_usda_catalogue.py --all
```

`--all` is deliberately explicit: the USDA catalogue is paged and imports are subject
to the provider's rate limits. Omit it to import one 200-item page for local testing.