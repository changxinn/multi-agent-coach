# Nutrition Agent Implementation Plan

## Goal

Upgrade Sam, the Nutrition Advisor, from a free-text meal logger into a persistent, user-scoped nutrition feature. The finished capability will calculate energy and macro targets, retrieve food nutrition data, create meal plans, log meals, track adherence, and provide nutrition context to the Training, Recovery, and Summarizer agents.

## Confirmed Decisions

- Use the existing PostgreSQL database configured through `DATABASE_URL` for all nutrition persistence.
- Do not add optional fields such as budget, cooking time, cuisine preferences, meal-count preference, or disliked foods in the first release.
- Required profile inputs are age, sex used for the energy equation, weight, height, activity level, fitness/nutrition goal, dietary preferences, dietary restrictions, and allergies.
- Use USDA FoodData Central as the initial food-data provider. Store its API key in `USDA_FDC_API_KEY` on the server only.
- Do not implement barcode support.
- Add `get_nutrition_context(user_id, for_date)` as a shared, read-only data contract for all agents.
- Create a user-facing Nutrition page using Ant Design tabs.
- Deploy a private Nutrition Agent microservice on port `8004` with `X-Internal-Service-Token` authentication.

## Development Environment (Mandatory)

All Python development, database migration, linting, and test commands for this repository **must** use the repo-local `.venv`. Do not use system or globally installed Python, as it can run against incompatible interpreter versions or dependencies.

From the `multi-agent-coach` repository root, either activate the environment:

```bash
source .venv/bin/activate
```

or invoke its interpreter explicitly (preferred for one-off commands):

```bash
.venv/bin/python -m pytest
```

## Implementation Status (September 2026)

| Phase | Status | Delivered scope |
| --- | --- | --- |
| Phase 1: Persistent foundation | Implemented | PostgreSQL nutrition tables, user-scoped profiles and target snapshots, deterministic calculator, structured meal CRUD, idempotency support, private Nutrition Agent, and authenticated gateway proxy routes. |
| Phase 2: Food data and user dashboard | Implemented; live catalogue load pending verification | USDA search/detail provider, persistent food cache, local catalogue route, daily summaries and adherence, four-tab Nutrition page, explicit-macro manual entries, USDA importer, and importer/parser coverage. Run a live bounded import with a configured USDA key before treating the catalogue as operational. |
| Phase 3: Planning and shared context | Not implemented | Shared nutrition context for Training/Recovery, verified meal-plan generation, substitutions, and target-review workflow extensions remain future work. |
| Phase 4: Quality and operations | Partially implemented | Focused calculator, route, provider, schema, and catalogue tests plus a one-off Compose importer job are present. Provider/cache metrics, audit history, scheduled refreshes, and end-to-end/safety coverage remain future work. |

### Delivered validation

- The nutrition-focused suite passed with **29 tests** after the USDA list-response parser correction.
- Python compilation passed for the USDA provider, importer, and catalogue tests; scoped `git diff --check` also passed.
- The frontend production build passed during the Meal Log implementation.
- `docker compose config --quiet` passed for both the normal stack and the `catalogue-import` profile.
- Docker image build/run validation was not performed here because the Docker daemon was unavailable. A live USDA import is likewise pending an environment that provides `USDA_FDC_API_KEY`.

## Current State and Gap

The current Nutrition Advisor can answer chat questions, write a free-text meal entry through `tools/log_meal.py`, and read the shared progress summary. Meals are stored in `data/user_data.json`, which is shared across users and unsuitable for durable multi-user tracking.

The existing `systemdb.user_fitness_profiles` table has fitness goal, level, weight, height, and age. It does not contain sex, activity level, dietary preferences/restrictions/allergies, target history, structured meals, food items, meal plans, or adherence data.

## Target Architecture

```text
Nutrition page / Chat
        |
        v
Gateway API ----> PostgreSQL nutrition tables
        |
        +----> Nutrition Agent :8004
                    |
                    +--> calculator and meal-plan engine
                    +--> USDA provider and local food cache
                    +--> get_nutrition_context read model
```

The LLM explains verified results, asks for missing information, and coaches the user. Deterministic code owns energy/macro calculations, nutrient values, restriction checks, persistence, and adherence scoring.

The public Gateway routes authenticate the user and pass the authenticated user ID to the private Nutrition Agent. Nutrition Agent operations are protected with `X-Internal-Service-Token`. The Meal Log's catalogue endpoint reads only from the Nutrition-owned local food cache; opening the food selector does not call USDA. USDA search/detail operations can populate or refresh individual cached foods.

## Persistent PostgreSQL Data Model

Add an idempotent migration such as `app/db/migrations/005_create_nutrition_tables.sql`. All tables must be under `systemdb`, reference `systemdb.users(id)`, and use `ON DELETE CASCADE`.

Implemented migrations are:

- `005_create_nutrition_tables.sql`: nutrition profiles, target snapshots, meals/items, plans, and planned meals.
- `006_add_nutrition_food_data_and_adherence.sql`: cached USDA foods, cached-food links on meal items, daily summaries, and catalogue indexes.
- `007_add_nutrition_idempotency.sql`: idempotency records for mutation operations.

Do not modify migration `006` after it has been applied in a shared environment. Add a new numbered migration for any later catalogue indexes or schema changes.

### `nutrition_profiles`

Keep nutrition data separate from `user_fitness_profiles`.

```text
user_id                    BIGINT PRIMARY KEY
sex_for_energy_equation    VARCHAR(16) NOT NULL
activity_level             VARCHAR(32) NOT NULL
nutrition_goal             VARCHAR(32) NOT NULL
dietary_preferences        JSONB NOT NULL DEFAULT '[]'
dietary_restrictions       JSONB NOT NULL DEFAULT '[]'
allergies                  JSONB NOT NULL DEFAULT '[]'
updated_at                 TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
```

Validate explicit allowed values for sex, activity level, and nutrition goal. Do not infer and save allergies or restrictions from chat without user confirmation.

### `nutrition_target_snapshots`

Persist every target calculation so historical adherence and plans remain reproducible.

```text
id                         BIGSERIAL PRIMARY KEY
user_id                    BIGINT NOT NULL
effective_from             DATE NOT NULL
effective_to               DATE
bmr_kcal                   INTEGER NOT NULL
tdee_kcal                  INTEGER NOT NULL
calorie_target_kcal        INTEGER NOT NULL
protein_target_g           NUMERIC(7,2) NOT NULL
carbohydrate_target_g      NUMERIC(7,2) NOT NULL
fat_target_g               NUMERIC(7,2) NOT NULL
fiber_target_g             NUMERIC(7,2) NOT NULL
calculation_method         VARCHAR(64) NOT NULL
calculation_inputs         JSONB NOT NULL
created_at                 TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
```

Only one snapshot is active for a user/date. A target recalculation closes the prior snapshot and creates a new record.

### Food cache, meals, and adherence

Create these additional tables:

- `nutrition_food_cache`: provider, provider food ID, description, serving data, nutrients per 100 g, allergen data, raw response, fetched timestamp, unique `(provider, provider_food_id)`.
- `nutrition_meals`: user, eaten timestamp, meal type, notes, source, optional planned-meal link, created timestamp.
- `nutrition_meal_items`: meal, optional cached-food link, food name, quantity/unit/grams, calories, protein, carbohydrates, fat, fiber, and source (`usda`, `manual_estimate`, or `meal_plan`).
- `nutrition_meal_plans`: user, target snapshot, date range, status, generated plan JSON, created timestamp.
- `nutrition_planned_meals`: plan, date, meal type, per-meal macro targets, meal contents JSON.
- `nutrition_daily_summaries`: user/date primary key, target snapshot, actual daily macros, meal count, calorie/protein/plan adherence percentages, updated timestamp.

USDA data may not contain complete allergen information. The product must label unknown allergen data as unknown, never as safe.

## Backend Services

### Nutrition profile and calculator

Add:

- `app/services/nutrition_profile_service.py`
- `app/services/nutrition_calculator.py`
- nutrition repositories under `app/db/repositories/`

The calculator must be pure and unit-tested. It should:

1. Verify the required data exists.
2. Calculate BMR with a documented Mifflin-St Jeor implementation.
3. Apply an explicit activity multiplier to calculate TDEE.
4. Apply versioned goal policies for maintenance, fat loss, muscle gain, or performance/endurance.
5. Calculate calorie, protein, carbohydrate, fat, and fiber targets.
6. Return structured values, calculation inputs, policy version, and missing fields.

Use decimal-safe arithmetic for nutrient values; round for presentation only.

### Food data provider

Add `app/services/food_data/` with a provider interface:

```python
class FoodDataProvider(Protocol):
    async def search_foods(self, query: str) -> list[FoodSearchResult]: ...
    async def get_food_details(self, provider_food_id: str) -> FoodDetails: ...
```

Implement `UsdaFoodDataCentralProvider` first. The provider needs timeout, retry, rate-limit handling, and persistent caching in `nutrition_food_cache`.

### Meal, plan, and adherence services

Implement services for:

- Meal create/list/update/delete and daily nutrient aggregation.
- Structured natural-language meal parsing with user confirmation or explicit estimate labeling.
- Deterministic meal-plan macro allocation, then USDA-backed food suggestions.
- Meal-plan substitutions that validate macro fit, dietary restrictions, and allergies.
- Daily/weekly adherence calculation.
- Target reviews that recommend a change but require explicit user confirmation to apply it.

## Shared `get_nutrition_context`

Create one reusable read model:

```python
async def get_nutrition_context(user_id: int, for_date: date) -> NutritionContext:
```

It returns:

- Confirmed allergies, dietary restrictions, and preferences.
- Active target snapshot and remaining daily calories/macros.
- Meals and daily actual totals, including estimated versus USDA-backed item counts.
- Recent seven-day adherence trends.
- Active planned meals for the requested date.
- `missing_data` and `data_quality_warnings`.

Sam uses it for recommendations. Training uses it for training-day fueling guidance, Recovery uses it to avoid aggressive deficit advice during poor recovery, and Summarizer uses it for target/adherence status. Other agents must use this function rather than directly querying nutrition tables.

## Nutrition Agent Tool Contract

Replace Sam's current `log_meal` and generic `progress`-only behavior with:

```text
get_nutrition_context
get_nutrition_profile
update_nutrition_profile
calculate_tdee
determine_macro_targets
get_active_nutrition_targets
search_food_database
get_food_nutrition
log_structured_meal
get_daily_nutrition_totals
get_nutrition_progress
generate_meal_plan
get_training_context
get_recovery_context
```

Required agent rules:

1. Ask focused questions when required target inputs are missing.
2. Never invent numeric nutrition values; use tool results or state that an entry is an estimate.
3. Check confirmed restrictions/allergies before food recommendations.
4. Use training and recovery context for meal timing and deficit recommendations.
5. Require explicit logging intent; request portion details where necessary.
6. Require explicit confirmation before saving nutrition profile changes or applying target adjustments.
7. Add a nutrition safety policy for clinical diets, eating-disorder language, unsafe target requests, and high-risk health conditions.

## Gateway API

Add authenticated, user-scoped routes under `app/api/routes/nutrition.py`:

```text
GET/PUT    /api/nutrition/profile
POST       /api/nutrition/targets/calculate
GET        /api/nutrition/targets/active
GET        /api/nutrition/foods/search?q=
GET        /api/nutrition/foods/{food_id}
POST       /api/nutrition/meals
GET        /api/nutrition/meals?date=
PUT/DELETE /api/nutrition/meals/{meal_id}
GET        /api/nutrition/daily-summary?date=
GET        /api/nutrition/adherence?from=&to=
POST       /api/nutrition/meal-plans
GET        /api/nutrition/meal-plans/active
```

Normal users may only access their own nutrition data. Do not make their meal records administrator-managed by default.

## Nutrition Page

Create `frontend/src/pages/NutritionPage/`, add `/nutrition` to `Routes`, `PageIds`, `routePages`, and `App.tsx`, and permit `User`, `Staff`, and `Admin` access.

Use Ant Design `Tabs`:

### Today

- `Statistic` and `Progress` displays for calories/macros consumed and remaining.
- Meal timeline for the selected date.
- Quick meal-log action.
- Warnings for missing targets, estimates, and unknown allergen metadata.

### Meal Log

- Paginated `Table` with date and meal-type filters.
- Add/edit/delete actions using `Modal`, `Form`, `AutoComplete` or `Select`, `InputNumber`, and `Popconfirm`.
- USDA food search and nutrient detail display.
- Clear labels for manually estimated items.

### Meal Plan

- Active plan using `Card`, `List`, and date selection.
- Per-meal portions and macro totals.
- Verified substitutions.
- Generate/refresh actions with loading and error states.

### Progress

- Seven-day adherence table/chart-ready summary for calories, protein, meals logged, and plan adherence.
- Active target snapshot information.
- Target-review action that requires confirmation before creating a new snapshot.

### Profile and Targets

- Required nutrition profile form.
- TDEE/macro calculation preview with assumptions and inputs.
- Explicit save-profile and apply-target actions.

Follow the existing React Query patterns in `RecoveryTablePage` for queries, mutations, cache invalidation, loading/error/empty states, and CRUD modals.

## Nutrition Agent Microservice and Compose

Create `services/nutrition_agent/` using the private FastAPI pattern used by the Head Coach and Recovery Agent. It needs:

```text
services/nutrition_agent/
  Dockerfile
  requirements.txt
  README.md
  app/
    config.py
    main.py
    schemas.py
    repository.py
    calculator.py
    food_provider.py
    agent.py
```

The service runs on `8004`, exposes `/health`, requires `X-Internal-Service-Token` for private operations, and uses the same PostgreSQL database through `DATABASE_URL`.

Add configuration:

```text
USE_NUTRITION_AGENT_SERVICE=false
NUTRITION_AGENT_URL=http://localhost:8004
USDA_FDC_API_KEY=
```

Register `nutrition-agent` in `docker-compose.yml` at `127.0.0.1:8004:8004`; the API connects using `http://nutrition-agent:8004`.

The current Compose file deliberately overrides root `.env` database values with its bundled `db` container. For a deployment using the existing external PostgreSQL instance, provide that external URL to both `api` and `nutrition-agent` through deployment secrets/environment settings rather than use the local Compose database default.

### USDA catalogue import operations

`services/nutrition_agent/import_usda_catalogue.py` is an explicit, one-off importer for the approved Foundation, SR Legacy, and Survey/FNDDS datasets. It pages USDA `/foods/list`, accepts the list endpoint's top-level nutrient-name shape as well as food-detail shapes, and caches only foods with energy, protein, carbohydrate, and fat values per 100 g. Cache writes upsert on `(provider, provider_food_id)`, so rerunning the import refreshes records without duplicates.

Run a bounded smoke import before the full import:

```bash
PYTHONPATH=services/nutrition_agent .venv/bin/python \
  services/nutrition_agent/import_usda_catalogue.py --max-pages 1

PYTHONPATH=services/nutrition_agent .venv/bin/python \
  services/nutrition_agent/import_usda_catalogue.py --all
```

The Nutrition Agent Docker image includes the importer. Compose defines a profile-gated, non-restarting `nutrition-catalogue-import` job, so normal `docker compose up` never starts a full import. Use the same image, database settings, and `USDA_FDC_API_KEY` as the API service:

```bash
docker compose run --rm nutrition-catalogue-import \
  python import_usda_catalogue.py --max-pages 1

docker compose run --rm nutrition-catalogue-import
```

## Delivery Status and Remaining Roadmap

### Phase 1: Persistent foundation

1. [x] Migration, models, schemas, repositories, and ownership authorization.
2. [x] Nutrition profile and target snapshot services.
3. [x] TDEE and macro calculator with unit tests.
4. [x] PostgreSQL-backed structured meal CRUD replacing JSON meal storage.
5. [x] Nutrition Agent service, gateway client/proxy, Docker image, and Compose registration.

### Phase 2: Food data and user dashboard

1. [~] USDA provider, persistent cache, food-query routes, and offline catalogue importer. The list-response parser is covered; execute a live bounded import with `USDA_FDC_API_KEY` to verify rows are inserted in the deployment environment.
2. [x] Daily totals and adherence calculations.
3. [x] Today, Meal Log, Profile and Targets, and Progress tabs. Meal Log uses one selector for locally cached USDA choices or a manual food name; manual entries require explicit calories, protein, carbohydrate, and fat values.
4. [ ] Sam's structured nutrition tool integration.

### Phase 3: Planning and shared context

1. [ ] Implement `get_nutrition_context`.
2. [ ] Integrate training and recovery read contexts.
3. [ ] Add verified daily meal plans, then multi-day plans.
4. [ ] Add substitutions and confirmed target reviews.

### Phase 4: Quality and operations

1. [~] Provider failure translation and focused provider/cache tests are implemented; provider/cache metrics remain outstanding.
2. [ ] Audit history for target changes, estimates, and plan revisions.
3. [~] Focused unit and route coverage is implemented; safety, end-to-end, and evaluation coverage remain outstanding.

## Test Plan and Acceptance Criteria

Implemented coverage includes BMR/TDEE and macro policy, input validation, USDA detail and list-response nutrient mapping, local catalogue delegation, manual-entry macro requirements, gateway route contracts/ownership handling, and Nutrition Agent service operations. Continue with restrictions/allergies, complete adherence scenarios, internal-token authentication, agent tool selection, Nutrition-page loading/error/empty/mutation states, safety, and end-to-end coverage.

The feature is complete when a user can save the required profile, receive versioned TDEE/macro targets, search USDA foods, log structured PostgreSQL meals, inspect daily totals and adherence, generate restriction-safe meal plans, and receive shared nutrition-aware coaching through Sam and the other agents.