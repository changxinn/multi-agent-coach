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
| Phase 2: Food data and user dashboard | Implemented | USDA search/detail provider, persistent food cache, local catalogue route, daily summaries and adherence, four-tab Nutrition page, explicit-macro manual entries, and a version-controlled USDA Foundation baseline catalogue. Migration `010` seeds 95 macro-complete foods without bundled JSON, a USDA API key, or a one-off import job. |
| Phase 3: Planning and shared context | Partially implemented | Versioned, user-scoped draft meal-plan persistence; private-agent and authenticated gateway create/get/list/confirm/archive/active-plan/context APIs; date-scoped target/plan context; confirmation-time allergen safety validation; idempotency; and atomic overlapping-plan supersession are implemented. Generation, frontend workflows, and consumption by Training, Recovery, and Summarizer remain pending. |
| Phase 4: Quality and operations | Partially implemented | Focused calculator, route, provider, schema, catalogue, and seed-migration contract tests are present. The static catalogue seed is idempotent and runs through the root application migration process. Provider/cache metrics, audit history, catalogue refresh policy, scheduled refreshes, and end-to-end/safety coverage remain future work. |

### Delivered validation

- The focused food-data, catalogue, gateway-route, and Nutrition Agent client suite passed with **47 tests**.
- Ruff passed for the Nutrition catalogue/provider changes, and `git diff --check` passed.
- Migration-runner compatibility was verified: migration `010` contains one semicolon-safe idempotent `INSERT` with **95** Foundation seed rows.
- Frontend lint and the production build passed during the Meal Log implementation.
- Meal-plan persistence, private-agent endpoint, gateway route, and gateway-client tests passed (**44 selected tests**). They cover date and duplicate-meal validation, target-snapshot ownership, user/date scoping, draft confirmation/archive transitions, confirmation-time allergen safety, idempotency forwarding, lifecycle `422` detail propagation, `503` failure translation, advisory-lock/version-allocation SQL, and overlapping-plan supersession SQL.
- `py_compile` passed for the modified nutrition gateway and private-agent modules; `git diff --check` passed.
- Docker image build/run validation and a live PostgreSQL migration application were not performed here because the Docker daemon was unavailable and `psql` is not installed in this environment.
- Migrations `008_add_nutrition_meal_plans.sql` and `009_make_nutrition_meal_plans_draft_by_default.sql` have been reported as applied, but this was not independently verified because `psql` is unavailable in this environment. Migration `009` changes the deployed database default from `active` to `draft`. PostgreSQL integration tests have not yet exercised lifecycle constraints or concurrent transactions.

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

- `005_create_nutrition_tables.sql`: nutrition profiles, target snapshots, and meals/items.
- `006_add_nutrition_food_data_and_adherence.sql`: cached USDA foods, cached-food links on meal items, daily summaries, and catalogue indexes.
- `007_add_nutrition_idempotency.sql`: idempotency records for mutation operations.
- `008_add_nutrition_meal_plans.sql`: versioned meal plans, structured planned meals, and optional meal-to-plan linkage.
- `010_seed_nutrition_foundation_food_cache.sql`: static, idempotent USDA Foundation baseline catalogue with 95 foods that have complete per-100 g energy, protein, carbohydrate, and fat data.

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

The base reusable read model is implemented in the private Nutrition Agent and exposed through the authenticated gateway:

```python
async def get_nutrition_context(user_id: int, for_date: date) -> NutritionContext:
```

The implemented contract returns the requested `date`, the user-owned target snapshot effective on that date (or `null`), and the user-owned active meal plan covering that date (or `null`). It is available at:

```text
POST /v1/nutrition/context       # private; X-Internal-Service-Token required
POST /api/nutrition/context      # authenticated gateway; body: {"date": "YYYY-MM-DD"}
```

The gateway derives `user_id` solely from the authenticated user; clients cannot select another user's context. The context is not yet consumed by Training, Recovery, or Summarizer.

Expand the read model before cross-agent use to include:

- Confirmed allergies, dietary restrictions, and preferences.
- Active target snapshot and remaining daily calories/macros.
- Meals and daily actual totals, including estimated versus USDA-backed item counts.
- Recent seven-day adherence trends.
- Active planned meals for the requested date.
- `missing_data` and `data_quality_warnings`.

Sam should use it for recommendations. Training should use it for training-day fueling guidance, Recovery should use it to avoid aggressive deficit advice during poor recovery, and Summarizer should use it for target/adherence status. Other agents must use this function rather than directly querying nutrition tables.

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
POST       /api/nutrition/profile/get
POST       /api/nutrition/profile/save
POST       /api/nutrition/targets/calculate
POST       /api/nutrition/targets/active
POST       /api/nutrition/foods/search
POST       /api/nutrition/foods/detail
POST       /api/nutrition/meals/create
POST       /api/nutrition/meals/list
POST       /api/nutrition/meals/replace
POST       /api/nutrition/meals/delete
POST       /api/nutrition/daily-summary
POST       /api/nutrition/adherence
POST       /api/nutrition/meal-plans/create
POST       /api/nutrition/meal-plans/active
POST       /api/nutrition/context
```

Normal users may only access their own nutrition data. Do not make their meal records administrator-managed by default.

Meal-plan creation accepts user-confirmed plan content linked to an existing target snapshot, not a generated recommendation. The public schema rejects caller-supplied `safety_status`, validates a zero-to-31-day inclusive date range, requires every planned meal to fall within the range, and rejects duplicate `(planned_date, meal_type)` entries. The gateway forwards `Idempotency-Key` for creation and translates Nutrition Agent transport or unexpected failures to `503 Service Unavailable`.

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

### USDA catalogue seed operations

`app/db/migrations/010_seed_nutrition_foundation_food_cache.sql` is the static,
version-controlled baseline catalogue. Migration `006` creates
`systemdb.nutrition_food_cache`; migration `010` inserts 95 USDA Foundation foods
that have energy, protein, carbohydrate, and fat values per 100 g. The root API
applies migrations automatically on startup, so the Nutrition Agent has no JSON
parsing, USDA pagination, or API-key requirement to serve this baseline catalogue.

The seed is deliberately idempotent:

```sql
ON CONFLICT (provider, provider_food_id) DO NOTHING
```

This preserves later curated or provider-refreshed records. Any future static
catalogue update should be a new ordered migration rather than editing migration
`010`, and should retain this conflict policy unless replacing existing records is
an intentional, reviewed decision.

## Delivery Status and Remaining Roadmap

### Phase 1: Persistent foundation

1. [x] Migration, models, schemas, repositories, and ownership authorization.
2. [x] Nutrition profile and target snapshot services.
3. [x] TDEE and macro calculator with unit tests.
4. [x] PostgreSQL-backed structured meal CRUD replacing JSON meal storage.
5. [x] Nutrition Agent service, gateway client/proxy, Docker image, and Compose registration.

### Phase 2: Food data and user dashboard

1. [x] USDA provider, persistent cache, food-query routes, and migration-seeded Foundation catalogue. The Meal Log reads the local cache only. Root migration `010` seeds 95 macro-complete Foundation foods with `ON CONFLICT (provider, provider_food_id) DO NOTHING`; it does not need a bundled export, USDA pagination, or an API key. Future larger catalogue snapshots must be added as new ordered migrations, never by editing `010`.
2. [x] Daily totals and adherence calculations.
3. [x] Today, Meal Log, Profile and Targets, and Progress tabs. Meal Log uses one selector for locally cached USDA choices or a manual food name; manual entries require explicit calories, protein, carbohydrate, and fat values.
4. [ ] Sam's structured nutrition tool integration.

### Phase 3: Planning and shared context

1. [x] Implement the date-scoped `get_nutrition_context` base contract containing the effective target snapshot and active meal plan, with private-agent and authenticated gateway endpoints.
2. [ ] Integrate the context contract into Sam, Training, Recovery, and Summarizer. Expand it with profile restrictions/preferences, daily totals/remaining macros, data-quality warnings, and adherence trends before relying on it for coaching.
3. [~] Versioned, user-scoped draft meal-plan persistence and authenticated gateway create/get/list/confirm/archive/active-plan routes are implemented. Creation explicitly persists `draft` status, including on deployments upgraded by migration `009_make_nutrition_meal_plans_draft_by_default.sql`. Confirmation re-evaluates safety, rejects allergen-blocked plans, acquires a per-user advisory lock, activates the draft, and atomically supersedes every overlapping `active` plan for that user; non-overlapping plans remain active. Confirm and archive use distinct idempotency-operation namespaces. Remaining work: deterministic generation; a Nutrition-page draft/list/inspect/confirm/archive workflow; planned-vs-logged adherence; and date-range plan browsing.
4. [x] Integrate confirmation-time food/allergen validation with dietary restrictions and allergies. It assigns `safe`, `review_required`, or `blocked`; a blocked plan cannot be confirmed. The gateway preserves private-agent lifecycle and safety `422` details rather than misclassifying them as incomplete profiles.
5. [x] Expose archive lifecycle operations and document status-transition/versioning rules. Only `draft` plans may be confirmed; only `draft` or `active` plans may be archived; `archived` and `superseded` plans reject further lifecycle transitions. Replacing an overlapping active plan transitions it to `superseded`.
6. [ ] Add substitutions and confirmed target reviews.

### Phase 4: Quality and operations

1. [~] Provider failure translation and focused provider/cache tests are implemented; provider/cache metrics remain outstanding.
2. [ ] Audit history for target changes, estimates, and plan revisions.
3. [~] Focused unit and route coverage is implemented, including meal-plan schema/service/repository/gateway/client contracts, safety/lifecycle rejections, and gateway `422` detail propagation. Add PostgreSQL integration tests for migrations `008`/`009`, status defaults, active-plan selection, supersession, version allocation, persisted idempotency, and advisory-lock concurrency; frontend, cross-agent, end-to-end, and evaluation coverage also remain outstanding.

## Test Plan and Acceptance Criteria

Implemented coverage includes BMR/TDEE and macro policy, input validation, USDA detail nutrient mapping, local catalogue delegation, static seed-migration completeness/idempotency, manual-entry macro requirements, gateway route contracts/ownership handling, Nutrition Agent service operations, and meal-plan/context client contracts. Meal-plan tests cover bounded date ranges, duplicate planned meals, user-owned target snapshots, draft/status transitions, confirmation-time allergen safety, active-plan user/date scoping, idempotency forwarding, lifecycle `422` detail propagation, failure translation, and repository SQL for advisory locking, version allocation, and supersession. Continue with live PostgreSQL migration/constraint/concurrency coverage, complete adherence scenarios, internal-token authentication, agent tool selection, Nutrition-page loading/error/empty/mutation states, cross-agent, and end-to-end coverage.

The feature is complete when a user can save the required profile, receive versioned TDEE/macro targets, search USDA foods, log structured PostgreSQL meals, inspect daily totals and adherence, generate restriction-safe meal plans, and receive shared nutrition-aware coaching through Sam and the other agents.