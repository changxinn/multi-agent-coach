# Nutrition Agent API Contract

Status: Canonical Phase 0 contract for implementation.

This document defines the executable first-release contract for public main-API nutrition routes and private Nutrition Agent routes. Public routes are mounted under `/api/nutrition`; private routes are mounted under `/v1/nutrition`. Any externally visible change requires a dated Section 14 decision in `C:\dev\multi-agent-coach\docs\nutrition_agent\NUTRITION-SERVICE-IMPLEMENTATION-PLAN.md` and an API-versioning assessment.

## Global conventions

- Every public route requires the existing JWT dependency and derives numeric `user_id` from `current_user["id"]`. Public request bodies/query parameters never accept `user_id`. Private user-scoped routes use `/users/{user_id}` and require `X-Internal-Service-Token` equal to `NUTRITION_INTERNAL_SERVICE_TOKEN`.
- Public timestamps are RFC 3339 datetimes with an explicit offset, serialized with `Z` for UTC. A calendar date is `YYYY-MM-DD`. Date-range endpoints require both `start_date` and `end_date` plus an IANA `timezone`; `start_date <= end_date`, inclusive range maximum 31 days. Invalid zones/ranges are validation failures.
- Offset pagination uses `limit=20` by default (`1..100`) and `offset=0` by default (`0..10000`). Each paginated response is `{items, limit, offset, total}`. Results are newest first unless stated otherwise.
- Strings are UTF-8 after outer-whitespace trimming; empty strings are rejected. Dietary restrictions/allergies are deduplicated case-insensitively while preserving first normalized display value. User descriptions, food queries, medical disclosures, tokens, upstream payloads, and exception text are not logged or metric labels.
- `PUT` means full replacement. There is no nutrition `PATCH` contract in this release. `204` responses have no body.

## Public errors and request IDs

Every response includes `X-Request-ID`: a caller-provided 1–128 printable non-whitespace ASCII value, otherwise a server-generated UUID. Every public nutrition error, including JWT dependency and validation failures, is exactly:

```json
{"error":{"code":"VALIDATION_ERROR","message":"Request validation failed.","request_id":"018f..."}}
```

The nutrition router registers route-scoped handlers/wrappers for `RequestValidationError`, `HTTPException`, rate-limit exceptions, and mapped Nutrition-client exceptions. It does not change legacy error shapes outside nutrition. Validation failures never return FastAPI `detail` arrays/rejected values. Unhandled exceptions are logged with request ID and return `500 INTERNAL_ERROR` with `An unexpected error occurred.`

| Status | Code | Stable public message | Use |
| --- | --- | --- | --- |
| 401 | `UNAUTHORIZED` | `Authentication is required.` | Missing/invalid/expired/disabled/malformed JWT. |
| 403 | `FORBIDDEN` | `You are not allowed to perform this action.` | Authenticated caller denied. |
| 404 | `NUTRITION_PROFILE_NOT_FOUND`, `MEAL_LOG_NOT_FOUND`, `NUTRITION_TARGET_NOT_FOUND`, `FOOD_NOT_FOUND`, `ASSESSMENT_NOT_FOUND` | `The requested nutrition resource was not found.` | Named resource absent or not owned. |
| 422 | `VALIDATION_ERROR` | `Request validation failed.` | Body/path/query/header/enum/timezone/range validation. |
| 422 | `NUTRITION_VALUE_INCONSISTENT` | `Nutrition values are inconsistent.` | Cross-field nutrition values are mathematically inconsistent: provided calories differ by more than 20% from 4 × (`protein_g` + `carbs_g`) + 9 × `fat_g`, or a provided serving quantity is incompatible with its per-serving nutrient values. |
| 422 | `NUTRITION_SAFETY_REFERRAL_REQUIRED` | Exact policy referral text. | Safety blocks calculate/save/meal plan. |
| 429 | `RATE_LIMITED` | `Too many requests. Please retry later.` | Includes integer `Retry-After` seconds. |
| 503 | `DEPENDENCY_UNAVAILABLE` | `Nutrition service is temporarily unavailable.` | Programmatic dependency failure. |
| 503 | `SERVICE_DISABLED` | `Nutrition service is not enabled.` | Master switch off or service not ready. |

## Shared value objects

`SafetyContext` is optional/request-scoped only on evaluate, calculate, save, and meal-plan requests:

```json
{"pregnancy_lactation_status":"unknown|not_pregnant_or_breastfeeding|pregnant|breastfeeding|pregnant_and_breastfeeding","medical_conditions":["diabetes|uses_insulin_or_glucose_lowering_medication|kidney_disease|heart_disease|hypertension|eating_disorder_history"],"risk_flags":["under_18|current_disordered_eating_behaviors|chest_pain_or_breathing_difficulty|fainting_or_severe_dizziness|purging_or_laxative_use|severe_food_restriction|rapid_weight_loss_request|other_medical_condition"]}
```

Absent fields make no assertion; lists are unique with at most six medical conditions; unknown enums fail `422`. A `SafetyFinding` is `{"code": string, "severity":"escalate|warning"}`. Its allowed codes/order, phrase detection, projections, and persistence limits are defined only in `SAFETY-POLICY.md`.

`NutritionProfile` has `dietary_preference` (`omnivore|vegetarian|vegan|pescatarian|other`, default `omnivore`), `dietary_restrictions` and `allergies` (each 0–20 strings, 1–80), `meals_per_day` (1–10, default 3), `activity_level` (`sedentary|light|moderate|active|very_active`), optional `age` (1–120), `gender` (`male|female|other`), `weight_kg` (>0 to 300), and `height_cm` (>0 to 250). Responses add `created_at`/`updated_at`; public responses omit `user_id`.

`MealLog` has `id`, `meal_type` (`breakfast|lunch|dinner|snack`), `description` (1–1000), optional `calories` (1–10000), optional `protein_g`, `carbs_g`, `fat_g` (each 0–2000), and `logged_at` RFC 3339 datetime. Create/replacement require every field except nutrients; `logged_at` defaults to service time on create. Replacement retains ID and changes `logged_at` only when supplied.

## Endpoint contract

| Capability | Public route | Private route | Success | Failure/fallback |
| --- | --- | --- | --- | --- |
| Profile | `GET`, `PUT`, `DELETE /profile` | equivalent under `/users/{user_id}/profile` | read/upsert `200 NutritionProfile`; delete `204` | missing `404 NUTRITION_PROFILE_NOT_FOUND`; mutations never locally fall back |
| Meal logs | `POST`, `GET /meal-logs`; `GET`, `PUT`, `DELETE /meal-logs/{meal_log_id}` | equivalent under `/users/{user_id}` | create `201`/replay `200`; reads `200`; delete `204` | missing/foreign ID `404 MEAL_LOG_NOT_FOUND`; mutations never fall back |
| Targets | `POST /targets/calculate`, `POST /targets`, `GET /targets/current` | equivalent under `/users/{user_id}` | calculate/current `200`; save `201` | calculate never mutates; absent current `404`; safety `422` |
| Daily history | `GET /history/daily` | `GET /users/{user_id}/history/daily` | `200 DailyNutritionHistory` | dependency failure `503`; insufficient evidence gives nullable adherence |
| Meal plan | `POST /meal-plans/generate` | `POST /users/{user_id}/meal-plans/generate` | `200 MealPlan` | never persists; safety `422`; dependency failure `503` |
| Foods | `GET /foods/search`, `GET /foods/{fdc_id}` | same paths | `200` normalized food objects | cache/no-key/outage metadata; unknown `404 FOOD_NOT_FOUND` |
| Assessment history | `GET /assessment-history` | `GET /users/{user_id}/assessment-history` | `200` paginated projection | dependency failure `503` |
| Chat evaluation | existing `/api/chat` | `POST /users/{user_id}/evaluate` | existing chat response | chat only falls back locally for disabled/rollout-excluded/timeout/5xx |

Direct public nutrition routes are not rollout-bucketed. With the master switch false they return `503 SERVICE_DISABLED`; with it true every authenticated user uses the ready Nutrition Agent. Rollout bucketing applies only to orchestrator/chat evaluation.

### Concrete routes and schemas

The following table is exhaustive for this release. A private route has the same request and response body as its public equivalent unless its path is explicitly noted. Private routes receive `user_id` only from the path; neither surface accepts it in a body. All identifiers are positive decimal integers. `created_at`, `updated_at`, and `logged_at` are RFC 3339 UTC timestamps. Public routes use the public error envelope; private routes may use `detail`, which must never be forwarded by `NutritionAgentClient`.

| Operation | Public route | Private route | Request and success response |
| --- | --- | --- | --- |
| Profile read | `GET /profile` | `GET /users/{user_id}/profile` | `200 NutritionProfile`; absent profile is `NUTRITION_PROFILE_NOT_FOUND`. |
| Profile replace | `PUT /profile` | `PUT /users/{user_id}/profile` | `NutritionProfileWrite`; `200 NutritionProfile`. Full validated upsert with last-write-wins semantics; no optimistic-concurrency header in this release. |
| Meal create | `POST /meal-logs` | `POST /users/{user_id}/meal-logs` | `MealLogCreate`; `201 MealLog`, or `200` for an identical idempotent replay. |
| Meal read/replace/delete | `GET /meal-logs/{meal_log_id}`, `PUT /meal-logs/{meal_log_id}`, `DELETE /meal-logs/{meal_log_id}` | `GET /users/{user_id}/meal-logs/{meal_log_id}`, `PUT /users/{user_id}/meal-logs/{meal_log_id}`, `DELETE /users/{user_id}/meal-logs/{meal_log_id}` | Read/replace returns `200 MealLog`; replace uses `MealLogCreate` as a full replacement; delete is `204`. Non-owned/missing is `MEAL_LOG_NOT_FOUND`. |
| Meal list | `GET /meal-logs` | `GET /users/{user_id}/meal-logs` | Required date-filter tuple or none; paginated `MealLog` items. |
| Current target | `GET /targets/current?date=YYYY-MM-DD` | `GET /users/{user_id}/targets/current?date=YYYY-MM-DD` | `date` defaults to the caller's current local date only when a profile timezone exists; otherwise it is required. `200 NutritionTarget` or `NUTRITION_TARGET_NOT_FOUND`. |
| Calculate/save target | `POST /targets/calculate`, `POST /targets` | `POST /users/{user_id}/targets/calculate`, `POST /users/{user_id}/targets` | `TargetCalculateRequest` returns `200 TargetCalculation`; `TargetSaveRequest` returns `201 NutritionTarget`. |
| Daily history | `GET /history` | `GET /users/{user_id}/history` | Required `start_date`, `end_date`, `timezone`; `200 DailyNutritionHistory`. |
| Food search/detail | `GET /foods`, `GET /foods/{fdc_id}` | `GET /foods`, `GET /foods/{fdc_id}` | Search returns `200 FoodSearchResponse`; detail returns `200 Food` or `FOOD_NOT_FOUND`. Foods are shared reference data and private food routes intentionally have no user path. |
| Meal plan | `POST /meal-plans` | `POST /users/{user_id}/meal-plans` | `MealPlanRequest`; `200 MealPlanResponse`; never persists a plan. |
| Evaluate/history | not directly public; existing `/api/chat` delegates only | `POST /users/{user_id}/evaluate`, `GET /users/{user_id}/assessment-history` | `AssessmentEvaluateRequest` is `{message, safety_context?, profile?}`. `profile`, when supplied, is a transient full `NutritionProfileUpsert` validated at the private boundary; chat supplies it only after an ownership-scoped profile read and local allowlist validation. It is never persisted in assessment history. The request returns `200 AssessmentEvaluation`; history returns paginated `AssessmentHistoryItem` items. |

`NutritionProfileWrite` is `{dietary_preference, dietary_restrictions, allergies, meals_per_day, timezone}`. `dietary_preference` is one of `omnivore|vegetarian|vegan|pescatarian|other`, default `omnivore`; restrictions and allergies are independently normalized string arrays of 0–20 items, each 1–80 characters; `meals_per_day` is an integer `1..6`, default `3`; and `timezone` is a required IANA name. `NutritionProfile` adds `created_at` and `updated_at`. Profile targets and biometric values are managed through immutable target versions, not profile writes.

`MealLogCreate` is `{meal_type, description, calories, protein_g, carbs_g, fat_g, logged_at}`. `meal_type` is `breakfast|lunch|dinner|snack`; `description` is plain text of 1–1,000 characters with control characters rejected; calories is an integer `0..10000`; each macro is a decimal number `0..2000` with at most two fractional digits; calories and all three macros are optional but at least one nutrient value is required; `logged_at` defaults to the request receipt time when omitted. When calories and all three macros are supplied, the inconsistency rule produces `NUTRITION_VALUE_INCONSISTENT`. `MealLog` adds `id`, `created_at`, and `updated_at`. Meal-list filtering is either absent or the complete `start_date`, `end_date`, `timezone` tuple; it uses offset pagination and newest `logged_at` first.

`TargetCalculateRequest` is `{age, gender, weight_kg, height_cm, activity_level, goal, requested_weekly_weight_change_kg?, safety_context?}`. Age is integer `13..120`; gender is `female|male|other|unknown`; weight is decimal `20..500` kg; height is decimal `80..260` cm; activity level is `sedentary|light|moderate|active|very_active`; goal is `maintain|lose|gain`; requested change is a decimal greater than 0 and no greater than 2 kg/week and is permitted only for `lose` or `gain`. `TargetSaveRequest` adds required `effective_from` and has no server-side default. `MacroTargets` is `{protein_g, carbs_g, fat_g}` with non-negative decimal values. `TargetCalculation` is `{bmr,tdee,recommended_calories,macro_targets,safety_findings,policy_version}`. `NutritionTarget` adds `{id,inputs,effective_from,effective_to,created_at}`; `effective_to` is null for the active version. The same date may not belong to two versions.

`Food` is `{fdc_id,name,brand,category,serving_size_g,nutrients,last_updated}`. `fdc_id` is a positive integer; `brand` and `category` are nullable strings; `serving_size_g` is a nullable positive decimal; `nutrients` is `{calories,protein_g,carbs_g,fat_g,fiber_g}`, where each value is nullable non-negative decimal per serving; and `last_updated` is UTC. No raw USDA identifier besides `fdc_id`, upstream payload, query echo, or provider error is exposed. Food search requires trimmed `q` of 1–100 characters, `limit` `1..50` defaulting to 20, and boolean `include_usda` defaulting to true; items sort by case-insensitive name then `fdc_id` ascending.

`SafetyFinding` is `{code,severity,message}`. `code`, ordering, severity, and user-safe message are exactly those defined by `SAFETY-POLICY.md`; raw trigger text is never present. `AssessmentEvaluateRequest` is `{message?, target_inputs?, safety_context?}`: at least one of `message` (1–2000 characters) or `target_inputs` is required, and `target_inputs` has the `TargetCalculateRequest` fields other than `safety_context`. `AssessmentEvaluation` is `{status,score,message,recommendations,tdee,macro_targets,safety_findings,escalation,policy_version,created_at}`. `status` is `green|amber|red|escalate`; score is integer `0..10`; `message` is the sanitized presentation; recommendations is a sanitized array of 0–10 strings; `tdee` and `macro_targets` are nullable; and `escalation` is null unless escalating, when it is `{"message": policy referral text, "urgent": boolean}`. `AssessmentHistoryItem` has this same projection plus `id`; it never includes request content, raw safety context, reasoning, or tool traces.

`MealPlanRequest` is `{target_inputs?, use_current_target?, start_date?, days, excluded_foods?, safety_context?}`. Exactly one of `target_inputs` and `use_current_target=true` is required; `start_date` defaults to the caller's current local date from profile timezone; `days` is integer `1..7`; and `excluded_foods` is a normalized array of 0–20 strings with the profile string rules. `MealPlanResponse` is the shape in this section's prior meal-plan definition; its `date` values are consecutive calendar dates beginning at `start_date`. A missing current target is `NUTRITION_TARGET_NOT_FOUND`.

### Meals, targets, history, plans

`POST /meal-logs` does not deduplicate create requests during development. Each valid create request produces a distinct meal-log record. API-level idempotency is deferred to pre-production hardening and, if introduced, requires a versioned API contract, a forward-only migration, replay/conflict semantics, retention policy, and concurrent-write integration coverage. List date filtering requires all of `start_date`, `end_date`, and `timezone` when any date filter appears.

`TargetCalculateRequest` and `TargetSaveRequest` fields and bounds are defined in the concrete-schema section above. Target save recomputes, closes the prior active target on the preceding local date, and creates an immutable version. Overlapping ranges fail validation.

`DailyNutritionHistory` is `{start_date,end_date,timezone,days_with_logs,days:[{date,meal_logs,calories,protein_g,carbs_g,fat_g,target_calories,calorie_adherence_percentage}],average_daily_calories,average_daily_protein_g,average_daily_carbs_g,average_daily_fat_g,calorie_adherence_percentage}`. Nutrient averages include only days having that nutrient. Adherence is `null` unless at least three logged days have applicable targets.

`MealPlanRequest` requires target-calculation inputs or current-target selector, `days` (1–7), optional `excluded_foods` (0–20 strings), optional safety context. Response is `{days:[{date,meals:[{meal_type,name,serving_description,calories,protein_g,carbs_g,fat_g}]}],total_calories,total_protein_g,total_carbs_g,total_fat_g,safety_findings,policy_version,disclaimer}` and is never implicitly saved.

## Foods, assessments, and resilience

This document is the sole authority for public food-search validation and response semantics. `FoodSearchResponse` is `{items:[Food],source:"cache|cache_and_usda|cache_only",upstream_status:"not_requested|fresh|unavailable|circuit_open",stale:boolean}`; Food and assessment field shapes are defined in the concrete-schema section above. The master implementation plan owns cache freshness/staleness windows, refresh/no-result suppression, and per-instance USDA quota controls; those controls must produce only these public response fields.

Private errors may use FastAPI `detail` but the client never forwards it. Its lifespan-managed `httpx.AsyncClient` uses connect/read/write/pool/total timeouts of `2s/5s/5s/2s/10s`; retries exactly once only for idempotent reads on connect/read timeout or `502/503/504` with full-jitter `[0,250ms]`; never retries mutations. Five qualifying failures in rolling 30 seconds open a circuit for 30 seconds, then permit one half-open probe. Circuit-open requests fail immediately as `DEPENDENCY_UNAVAILABLE`. This is the sole client-resilience policy.