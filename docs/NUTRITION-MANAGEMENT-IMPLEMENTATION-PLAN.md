# Nutrition Management — Implementation Plan

**Status:** Planned; implementation not started  
**Scope owner:** Main FastAPI application and frontend  
**Related contract:** `C:\dev\multi-agent-coach\docs\nutrition_agent\API-CONTRACT.md`  
**Default timezone:** `Asia/Singapore`

---

## 1. Objective

Deliver authenticated Nutrition Management pages and APIs for managing a user's nutrition profile, meal logs, cached food reference data, immutable nutrition targets, daily history, dashboard metrics, and safe assessment history.

This capability belongs to the existing main FastAPI app. It uses the app's injected async SQLAlchemy database session for direct PostgreSQL persistence and does **not** call `NutritionAgentClient` or duplicate USDA/cache-refresh behaviour.

## 2. Decisions and Non-Negotiable Constraints

- All new endpoints are under `/api/nutrition-management/*` and are **POST-only**.
- Authentication derives the user identity from the existing JWT dependency. Request bodies and client-provided query values must never include or select `user_id`.
- Every user-owned query and mutation is constrained by the authenticated user ID.
- Missing resources and resources owned by another user return the same not-found response.
- Food reference lookup reads only `systemdb.food_cache`; it must not contact USDA or refresh cache contents.
- Nutrition targets are immutable revisions. Updating/replacing a target creates a new version rather than modifying a historical row.
- Assessment APIs return only a safe projection. They must exclude raw legacy response content, source/reasoning fields, internal tool traces, and any other non-presentation data.
- All new Pydantic request models use `extra="forbid"`.
- Continue existing sanitized nutrition error handling and request-ID behaviour for the new route prefix.

## 3. Singapore Timezone Policy

`Asia/Singapore` is the default IANA timezone for Nutrition Management.

1. Add a new forward-only migration; do not edit historical migrations.
2. Change the `nutrition_profiles.timezone` database default from `UTC` to `Asia/Singapore`.
3. Migrate every existing nutrition profile with `timezone = 'UTC'` to `Asia/Singapore`, as explicitly approved.
4. Default profile creation, omitted API timezone fields, and the frontend profile form to `Asia/Singapore`.
5. Preserve every existing non-UTC saved timezone and honour a user's saved valid timezone in user-specific date aggregation and display.
6. Validate all supplied timezone values as IANA names using `zoneinfo.ZoneInfo`.

## 4. Endpoint Surface

Implement typed POST handlers under `/api/nutrition-management` (exact route naming should align with existing route conventions):

| Capability | Operation |
| --- | --- |
| Dashboard | Retrieve summary, current target, recent activity, and relevant daily totals |
| Profile | Retrieve and upsert authenticated user's nutrition profile |
| Meals | List, create, retrieve, replace, and delete authenticated user's meal logs |
| Foods | Cache-only search and food-detail lookup from `food_cache` |
| Targets | Retrieve current/listed targets, calculate a candidate, and save an immutable target revision |
| History | Retrieve daily nutrition totals and target adherence for a bounded date range |
| Assessments | Retrieve paginated, redacted assessment history |

All reads use POST request bodies so the public management surface remains POST-only. Resource identifiers are path parameters only where consistent with current API conventions; ownership remains server-enforced.

## 5. Backend Implementation Design

### 5.1 Schemas

Create `C:\dev\multi-agent-coach\app\api\schemas\nutrition_management.py`.

Include strict request/response contracts for each operation, shared enums, pagination, and safe projections. Validation must cover:

- IANA timezone strings, defaulting to `Asia/Singapore` when omission is allowed;
- pagination offset/limit bounds;
- start/end date ordering and a maximum 31-day inclusive range;
- meal timestamps and supported meal-type enums;
- bounded descriptions, search terms, numeric nutrients, arrays, and free-text values;
- profile dietary-preference/activity/gender values;
- target inputs and target revision payloads;
- assessment filters and safe history response fields.

Do not accept `user_id`, raw assessment records, USDA refresh controls, or unknown fields.

### 5.2 Direct-Persistence Service

Create `C:\dev\multi-agent-coach\app\services\nutrition_management_service.py`.

The service receives the main app's injected async database session and authenticated user ID. It will:

- load/create and upsert profiles while retaining valid saved timezones;
- create and manage meal logs with ownership-scoped fetch/update/delete operations;
- search and retrieve food cache entries without upstream calls;
- calculate targets using parity-preserving validated logic and persist new immutable revisions;
- select a current/effective target deterministically by effective date and version;
- aggregate local-day meal data using the selected/saved IANA timezone;
- apply the relevant target revision to each daily history row for adherence calculations;
- produce dashboard values from the same scoped aggregate queries;
- read assessments with pagination and map only approved safe output fields.

For target calculation logic, prefer extracting framework-independent pure helpers from the Nutrition Agent when this can be done without changing public agent behaviour. If extraction would create risky coupling, implement an equivalent pure main-app helper and add explicit parity tests against approved representative cases.

### 5.3 Router and Application Wiring

Create `C:\dev\multi-agent-coach\app\api\routes\nutrition_management.py` and register it from `C:\dev\multi-agent-coach\app\main.py`.

- Use the established authenticated-user dependency and async-session dependency.
- Translate validation, missing resource, and persistence failures using established API error conventions.
- Apply the same sanitized nutrition exception/request-ID middleware or route handling used by `/api/nutrition` to `/api/nutrition-management`.
- Do not import or invoke `NutritionAgentClient` from this router/service.

### 5.4 Database Migration

Add the next immutable migration in `C:\dev\multi-agent-coach\app\db\migrations\` after confirming the migration ledger's current highest version.

The migration must:

```sql
ALTER TABLE systemdb.nutrition_profiles
    ALTER COLUMN timezone SET DEFAULT 'Asia/Singapore';

UPDATE systemdb.nutrition_profiles
SET timezone = 'Asia/Singapore'
WHERE timezone = 'UTC';
```

It must be idempotent where the project's migration framework requires it, preserve non-UTC values, and be registered/validated by the existing migration process.

## 6. Frontend Implementation Design

Update the existing React frontend without introducing unconfirmed dependencies.

### 6.1 Navigation and Routes

Update the existing page and route constants, sidebar navigation, application route configuration, and protected-route definitions for:

- Nutrition Dashboard
- Nutrition Profile
- Meals
- Targets
- Foods
- Assessments

### 6.2 Typed API Integration

Use the established `api.post(...)` client pattern. Add typed API functions and hooks consistent with current frontend conventions for the management routes. Requests must not send `user_id`.

### 6.3 Pages and States

Implement pages/components for the six Nutrition Management areas with consistent existing layout and visual conventions. Each view must provide loading, error, empty, and successful-content states. Mutations (meal deletion, target save/revision, profile save) require clear confirmation and feedback.

The Profile page must initially select `Asia/Singapore`; an existing returned profile timezone always overrides that initial form default.

## 7. Test Plan

Add focused backend tests consistent with repository conventions for:

- authentication required and JWT identity scoping;
- same not-found response for missing and non-owned profile/meal/target resources;
- rejection of `user_id`, unknown fields, invalid IANA zones, invalid enums, invalid dates, over-31-day ranges, and out-of-range pagination/numeric input;
- Singapore defaults in schema, service fallback, frontend request/form defaults as applicable, and migration SQL;
- migration of UTC rows only, preserving non-UTC profiles;
- cache-only food search/detail behaviour and proof no agent/USDA client is invoked;
- immutable target revision semantics, including deterministic same-effective-date version selection;
- local-day aggregation and target adherence in `Asia/Singapore` and an explicitly selected alternate saved timezone;
- dashboard aggregation correctness;
- assessment redaction (including absence of `response`, raw content, `tool_trace`, source/reasoning, and other unsafe fields);
- request ID and sanitized error behaviour for the new prefix;
- target-calculation parity if logic is duplicated rather than shared.

Add frontend tests only where the existing frontend test tooling and conventions support them; at minimum validate TypeScript/lint/build successfully.

## 8. Implementation Checklist

### Discovery and Design

- [ ] Confirm the current highest migration number and migration-runner conventions.
- [ ] Confirm current async SQLAlchemy session dependency and transaction conventions.
- [ ] Confirm frontend routing, API, state-management, and test conventions before implementation.
- [ ] Decide whether target helpers can be safely extracted from Nutrition Agent code or require a parity-tested main-app implementation.

### Database and Schema

- [ ] Add a new immutable migration setting the profile timezone default to `Asia/Singapore`.
- [ ] Migrate existing `UTC` profile timezone values to `Asia/Singapore`.
- [ ] Preserve existing non-UTC profile timezones.
- [ ] Add strict Nutrition Management Pydantic request/response schemas.
- [ ] Implement all required bounds, IANA timezone, date-range, enum, and unknown-field validation.

### Backend Service and API

- [ ] Implement `NutritionManagementService` with injected async DB session use.
- [ ] Implement ownership-scoped profile retrieval and upsert.
- [ ] Implement ownership-scoped meal list/create/read/replace/delete.
- [ ] Implement cache-only food search and detail retrieval.
- [ ] Implement target calculation and immutable revision persistence.
- [ ] Implement deterministic current-target selection by effective date/version.
- [ ] Implement timezone-aware daily history/adherence aggregation.
- [ ] Implement dashboard aggregation.
- [ ] Implement safe, paginated assessment-history projection.
- [ ] Add authenticated POST-only nutrition-management router.
- [ ] Register the router and sanitized error/request-ID handling in `app/main.py`.
- [ ] Verify no management route/service calls `NutritionAgentClient`.

### Frontend

- [ ] Add nutrition page and route constants.
- [ ] Add protected Nutrition Management application routes.
- [ ] Add sidebar/navigation entries.
- [ ] Add typed POST API functions and hooks.
- [ ] Implement Dashboard page and all loading/error/empty states.
- [ ] Implement Profile page with `Asia/Singapore` initial default.
- [ ] Implement Meals page and mutation confirmations.
- [ ] Implement Targets page with calculation, revision-save, and confirmation flow.
- [ ] Implement Foods cache-search page.
- [ ] Implement Assessments page with safe-history presentation.

### Validation and Release Readiness

- [ ] Add service/router/schema/migration tests listed in Section 7.
- [ ] Add target-calculation parity tests if helpers are not shared.
- [ ] Run focused Nutrition Management pytest coverage.
- [ ] Run relevant full backend test suite.
- [ ] Run the migration validation/runner process in the project-supported environment.
- [ ] Run `npm run lint` from `C:\dev\multi-agent-coach\frontend`.
- [ ] Run `npm run build` from `C:\dev\multi-agent-coach\frontend`.
- [ ] Verify edited/new files and confirm unrelated working-tree changes were not overwritten or reverted.
- [ ] Update API documentation if actual route names/contracts differ from this plan.

## 9. Definition of Done

The feature is complete only when direct, authenticated, POST-only Nutrition Management APIs and protected frontend pages work end-to-end; all user data is ownership-scoped; food reads remain cache-only; targets retain immutable revisions; assessment responses are demonstrably redacted; Singapore is the default and existing UTC profile values are migrated; and the validation commands in Section 8 pass.