# Nutrition Food Compatibility Enrichment Implementation Plan

## Goal

Safely expand meal-plan generation beyond the existing USDA nutrient cache by adding Nutrition-owned, curated food compatibility metadata. The implementation must honor persisted allergies, dietary preferences, and dietary restrictions without inferring safety from a food name at request time.

The initial acceptance and regression scenario is generating a usable plan for a profile with:

- dietary preference: Vegetarian;
- dietary restriction: Halal; and
- allergy: Milk.

The solution must protect the allergy and must not suggest removing it as a workaround.

This scenario does not limit the implementation scope. The architecture must support every predefined allergy, dietary preference, and dietary restriction for which the product defines an explicit compatibility policy and has reviewed metadata. All selected strict constraints are cumulative: a candidate must satisfy every declared allergy and every selected strict preference/restriction. Custom values remain advisory until the product defines their policy, evidence standard, and tests.

## Current State

`nutrition_food_cache` stores USDA-derived descriptions, serving details, macro nutrients, a provider raw response, and cache-level allergen fields. The current seed catalogue contains approximately 13,365 USDA rows, but its allergen metadata is predominantly `unknown`. The supplied USDA seed records do not consistently include complete ingredients, manufacturer allergen declarations, cross-contact information, or halal/kosher certification.

The current shared eligibility function in `services/nutrition_agent/app/meal_plan_eligibility.py` excludes food explicitly identified by USDA as containing ethyl alcohol. Existing allergy protections reject unknown allergen data when a user has an allergy. Vegetarian, halal, and other saved dietary values are not yet deterministically enforced during candidate selection.

## Safety Principles and Non-Goals

### Fail closed for safety-relevant constraints

For an allergy or strict dietary restriction, missing, unknown, inferred-only, or unreviewed compatibility data is ineligible for automatic meal planning. A food must have known compatible metadata to be selected.

This applies identically to deterministic fallback generation, the LLM catalogue-browsing tool, and confirmation-time validation.

### Separate cached data from approved planning data

The USDA cache remains useful for food lookup and manual meal logging even when a food is not safe enough for automatic planning. The meal planner must use the additional compatibility layer; it must not reinterpret USDA descriptions directly while serving a plan-generation request.

### LLM assistance is not authoritative food-safety verification

An LLM may classify and triage records in a managed batch process, but it must not independently certify:

- absence of an allergen or cross-contact risk;
- halal or kosher status/certification;
- gluten-free certification or manufacturing cross-contact status;
- vegetarian/vegan suitability of ambiguous prepared or branded food;
- low-FODMAP compatibility.

LLM-derived metadata is evidence for review and is never a reason to weaken fail-closed behaviour.

### Out of scope for the first implementation

- Caching the complete USDA catalogue as automatically safe.
- Inferring ingredient lists or certifications from food names.
- Replacing an authoritative ingredient, manufacturer, or certification source.
- Automatically approving branded and multi-ingredient foods solely from LLM output.
- Serving-size-specific low-FODMAP policy.
- Medical advice.

## Data Model

Keep the existing `nutrition_food_cache` table unchanged as the provider cache. Add a Nutrition Agent migration that creates `nutrition_food_compatibility`, one record per cached food.

```sql
CREATE TABLE IF NOT EXISTS nutrition_food_compatibility (
    food_cache_id BIGINT PRIMARY KEY
        REFERENCES nutrition_food_cache(id) ON DELETE CASCADE,

    review_status VARCHAR(24) NOT NULL DEFAULT 'pending'
        CHECK (review_status IN (
            'pending', 'auto_classified', 'approved', 'rejected', 'review_required'
        )),
    classification_version VARCHAR(64) NOT NULL,
    classification_source VARCHAR(64) NOT NULL,
    classified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMPTZ,
    reviewed_by VARCHAR(128),

    food_category VARCHAR(64),
    processing_level VARCHAR(24) NOT NULL DEFAULT 'unknown'
        CHECK (processing_level IN ('single_ingredient', 'prepared', 'branded', 'unknown')),

    allergen_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (allergen_status IN ('known', 'unknown')),
    allergens JSONB NOT NULL DEFAULT '[]'::jsonb,

    vegetarian_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (vegetarian_status IN ('suitable', 'unsuitable', 'unknown')),
    vegan_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (vegan_status IN ('suitable', 'unsuitable', 'unknown')),
    pescatarian_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (pescatarian_status IN ('suitable', 'unsuitable', 'unknown')),
    halal_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (halal_status IN ('suitable', 'unsuitable', 'unknown')),
    kosher_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (kosher_status IN ('suitable', 'unsuitable', 'unknown')),
    gluten_free_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (gluten_free_status IN ('suitable', 'unsuitable', 'unknown')),
    dairy_free_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (dairy_free_status IN ('suitable', 'unsuitable', 'unknown')),
    egg_free_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (egg_free_status IN ('suitable', 'unsuitable', 'unknown')),
    soy_free_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (soy_free_status IN ('suitable', 'unsuitable', 'unknown')),
    nut_free_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (nut_free_status IN ('suitable', 'unsuitable', 'unknown')),
    no_pork_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (no_pork_status IN ('suitable', 'unsuitable', 'unknown')),
    no_beef_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (no_beef_status IN ('suitable', 'unsuitable', 'unknown')),
    alcohol_free_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
        CHECK (alcohol_free_status IN ('suitable', 'unsuitable', 'unknown')),

    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence VARCHAR(16) NOT NULL DEFAULT 'low'
        CHECK (confidence IN ('low', 'medium', 'high')),
    reviewer_notes TEXT
);

CREATE INDEX IF NOT EXISTS nutrition_food_compatibility_planning_idx
    ON nutrition_food_compatibility (
        review_status, allergen_status, vegetarian_status, halal_status
    );
```

`evidence` must preserve the basis and provenance of every determination. For example, it may include the USDA description, category decision, source URL or certification reference where available, classifier version, and reviewer correction history. Do not store hidden model reasoning.

## Compatibility Semantics

### Review lifecycle

| Status | Meaning | Eligible for strict automatic planning? |
| --- | --- | --- |
| `pending` | No compatibility classification has been performed. | No |
| `auto_classified` | Batch classifier supplied preliminary metadata. | No |
| `review_required` | The item is ambiguous, processed, branded, low-confidence, or certification-dependent. | No |
| `approved` | Metadata has passed deterministic policy and any required human review. | Yes, if each requested constraint is `suitable` and allergen data is known/non-conflicting. |
| `rejected` | Record is unsuitable or cannot safely support meal planning. | No |

### Status values per constraint

Every compatibility field uses `suitable`, `unsuitable`, or `unknown`.

- `suitable`: the reviewed policy and evidence support selection for this constraint.
- `unsuitable`: the food conflicts with this constraint.
- `unknown`: data is insufficient; it is not a safety approval.

### Strict constraints

The first release deterministically enforces these saved values when selected:

| Normalized saved value | Required field |
| --- | --- |
| `vegetarian` | `vegetarian_status = suitable` |
| `vegan` | `vegan_status = suitable` |
| `pescatarian` | `pescatarian_status = suitable` |
| `halal` | `halal_status = suitable` |
| `kosher` | `kosher_status = suitable` |
| `gluten_free` | `gluten_free_status = suitable` |
| `dairy_free` | `dairy_free_status = suitable` |
| `egg_free` | `egg_free_status = suitable` |
| `soy_free` | `soy_free_status = suitable` |
| `nut_free` | `nut_free_status = suitable` |
| `no_pork` | `no_pork_status = suitable` |
| `no_beef` | `no_beef_status = suitable` |
| `alcohol_free` | `alcohol_free_status = suitable`, plus the existing USDA ethyl-alcohol check |
| `low_sodium` | Advisory in the initial release; requires a documented sodium threshold, nutrient-data completeness rule, and serving-size policy before strict enforcement. |
| `low_fodmap` | Advisory in the initial release; requires reviewed, serving-size-specific FODMAP evidence before strict enforcement. |

### Allergies

The predefined allergy options are `milk`, `eggs`, `peanuts`, `tree_nuts`, `soy`, `wheat`, `fish`, `shellfish`, and `sesame`. For every declared allergy, require `allergen_status = known` and require that the normalized allergen is absent from `allergens`. Unknown allergen data remains rejected whenever the user has one or more allergies.

Allergy checks are cumulative. For example, a user with milk and egg allergies can receive only approved foods whose known allergen list contains neither milk nor eggs. A food with known milk-free data but unknown egg data remains ineligible for that combined profile.

Do not treat `dairy_free_status`, `egg_free_status`, or another broad suitability flag as a substitute for known allergen metadata. The allergy check always uses confirmed, normalized allergen data and remains independent of dietary preference/restriction checks.

Custom values, and predefined values intentionally deferred from strict enforcement such as `low_sodium` and `low_fodmap`, are retained in the profile and shown to the LLM as advisory context, but must not be falsely enforced or falsely marked safe. A future policy addition must define the normalization, evidence standard, status column, and tests before becoming strict.

### Soft preferences

The predefined ranking-only preferences are `mediterranean`, `plant_forward`, `high_protein`, `low_carb`, `whole_food_focused`, `spicy_food`, `budget_friendly`, and `quick_prep_meals`. They should rank already compatible candidates or guide LLM selection; they must not reject otherwise safe foods in the initial release. `vegetarian`, `vegan`, and `pescatarian` are exceptions because they appear in the strict-constraint table and are enforced when selected.

## Catalogue Enrichment Pipeline

### 1. Define deterministic policy first

Add `services/nutrition_agent/app/food_compatibility_policy.py` containing:

- normalized profile-value aliases;
- strict constraint-to-column mappings;
- allowed initial auto-approval categories;
- prohibited automatic approval cases;
- approval rules and validation helpers;
- policy version.

Initial narrowly auto-approvable categories should be limited to clearly described, unprocessed foods such as fresh fruit, fresh vegetables, plain legumes, plain grains, and plain starchy vegetables. The exact category policy must be documented and tested.

Processed foods, branded foods, mixed recipes, animal-derived foods, and foods requiring certification are routed to review unless an authoritative reviewed source exists.

### Preliminary halal/kosher whole-food planning labels

The versioned whole-food policy may set `halal_status = suitable` and `kosher_status = suitable` for a food only when an authorized reviewer confirms that the cached record is a clearly described, unprocessed, single-ingredient whole food with no material ingredient, animal-source, alcohol, processing, or certification ambiguity. Initial examples include raw tomatoes, raw potatoes, plain fruit and vegetables, dry legumes, plain rice, and plain water.

This is a narrow application meal-planning eligibility determination under a documented policy such as `unprocessed_whole_food_v1`. It is **not** a halal or kosher certification claim and must never be presented in the API, LLM prompt, or UI as “certified halal” or “certified kosher.” The evidence must record the policy version, reviewer, review timestamp, and the USDA description used for the decision.

The rule does not cover packaged, canned, flavoured, branded, mixed, prepared, animal-derived, or otherwise ambiguous foods. Commercial hummus, canned or seasoned vegetables, tofu/tempeh without separately reviewed evidence, sauces, supplements, meat, fish, gelatin, enzymes, and alcohol-containing foods remain `unknown` or `review_required` until an authorized reviewer records sufficient authoritative evidence or certification. The absence of pork is never sufficient evidence of halal status.

### 2. Create a Pydantic contract for LLM classification

Add a model under the Nutrition Agent for a constrained JSON result. It should accept only:

- a controlled food category;
- processing level;
- explicitly named allergens, not inferred absence of allergens;
- vegetarian, vegan, and pescatarian status;
- explicit pork, beef, and alcohol presence when named;
- confidence and concise, visible evidence references.

The model must reject narrative-only output and unknown extra fields. The classifier prompt must clearly prohibit food-safety or certification claims that cannot be supported by supplied evidence.

The LLM must not output authoritative halal, kosher, gluten-free, or cross-contact-safe determinations. The deterministic policy derives narrowly allowed outcomes or leaves them unknown.

### 3. Add a non-interactive batch command

Create `scripts/enrich_nutrition_food_compatibility.py` with options equivalent to:

```text
.venv\Scripts\python.exe scripts\enrich_nutrition_food_compatibility.py --provider usda --batch-size 25 --dry-run
.venv\Scripts\python.exe scripts\enrich_nutrition_food_compatibility.py --provider usda --batch-size 25 --apply
.venv\Scripts\python.exe scripts\enrich_nutrition_food_compatibility.py --provider usda --resume-after-id 123 --report output.json
```

The command must:

1. Query cache records lacking a current classification version, in stable ID order.
2. Supply only necessary data to the classifier: cache ID, provider ID, description, source data type if present, current allergen fields, and relevant raw-response fields.
3. Validate every LLM result against the Pydantic schema.
4. Apply deterministic policy validation; never trust a model result directly for planning approval.
5. Upsert compatibility metadata, including source, version, timestamps, confidence, and evidence.
6. Leave a resumable audit/report artifact containing record IDs, input hashes, proposed results, errors, and review status.
7. Rate-limit requests, retry bounded transient failures, and avoid reclassifying unchanged records unless `--force` is provided.
8. Require `--apply` before any database write; default to `--dry-run` behaviour.

The command must not run during a user meal-plan request.

### 4. Deterministic post-validation and approval

Implement a policy function conceptually equivalent to:

```python
def determine_review_status(classification: CompatibilityClassification) -> str:
    if classification.confidence != "high":
        return "review_required"
    if classification.processing_level != "single_ingredient":
        return "review_required"
    if classification.food_category not in AUTO_APPROVABLE_CATEGORIES:
        return "review_required"
    return "auto_classified"
```

`auto_classified` records require either a bounded, documented automatic approval rule for low-risk unprocessed plant foods or an explicit human transition to `approved`. Certification-dependent attributes must remain `unknown` unless backed by a reviewed authoritative source.

The policy may record a food as positively incompatible when its description explicitly identifies an ingredient (for example, milk, egg, pork, beef, fish, shellfish, or alcohol). It must never infer that a food is allergen-free because an allergen is absent from the description.

### 5. Reviewer workflow

Initially provide an exportable JSON/CSV report and a repository/admin operation for reviewer updates. A later UI may add an administrative review screen.

The review operation must allow an authorized reviewer to approve, reject, or correct classifications and record:

- reviewer identity;
- review timestamp;
- authoritative source or certification reference;
- corrected compatibility fields;
- reviewer notes.

No review interface should imply a clinical or religious certification beyond the evidence captured.

## Initial Curated Catalogue

Seed enough reviewed items to support safe macro-balanced plans before enabling the restrictive generation path. Prioritize existing cache records for plainly described whole foods:

- fruit and vegetables;
- rice, potatoes, quinoa, and other reviewed grains;
- beans, lentils, and chickpeas;
- seeds and other foods only when relevant allergen metadata is complete;
- tofu only when soy status is correctly represented and the user does not avoid soy.

The initial seeded coverage must support the Vegetarian + Halal + Milk allergy acceptance scenario. This is a regression case, not the only supported combination. A food is eligible for any profile only when it is `approved`; has known, non-conflicting allergen metadata for every selected allergy; and has `suitable` status for every selected strict preference and restriction. Therefore, the initial scenario additionally requires no listed milk, `vegetarian_status = suitable`, and `halal_status = suitable` under documented evidence/policy.

Commercial hummus, composite recipes, branded products, products with incomplete ingredients, and uncertified certification-dependent products remain unavailable for restricted automatic plans until reviewed. They can remain searchable for manual logging with their data-quality status visible where applicable.

## Meal-Plan Integration

### Repository access

Extend `services/nutrition_agent/app/repository.py` with a catalogue query that joins `nutrition_food_cache` and `nutrition_food_compatibility`. It must return the compatibility fields needed for generation and confirmation-time checks.

The query must not globally require `approved`; unrestricted generation may support a carefully defined broader path later. For any user with allergies or strict constraints, only approved metadata with suitable/known outcomes may be returned. Query-level narrowing is an optimization, not the sole safety barrier.

### One shared eligibility function

Extend `services/nutrition_agent/app/meal_plan_eligibility.py` into the authoritative compatibility policy entry point. Preserve the existing ethyl-alcohol exclusion.

Conceptually:

```python
def is_food_compatible_for_meal_plan(
    food: dict[str, Any],
    compatibility: dict[str, Any] | None,
    profile: dict[str, Any],
) -> bool:
    if not is_eligible_for_meal_plan(food):
        return False
    if compatibility is None or compatibility["review_status"] != "approved":
        return False
    if not has_known_non_conflicting_allergen_data(compatibility, profile["allergies"]):
        return False
    if not satisfies_strict_preferences(compatibility, profile["dietary_preferences"]):
        return False
    return satisfies_strict_restrictions(compatibility, profile["dietary_restrictions"])
```

Normalize profile values once and use explicit aliases; never use substring matching or food-name inference to implement restrictions.

The exact same function must be used by:

1. deterministic fallback generation in the Nutrition Agent service;
2. `MealPlanLLMGenerator` catalogue browsing (`browse_cached_usda_foods`);
3. submitted-plan validation; and
4. confirmation-time safety validation.

The LLM may only receive food IDs that passed this filter. It cannot select arbitrary cache entries, and all submitted IDs are rechecked server-side.

### Candidate ranking

After strict filtering, rank candidates using nutrition targets and soft preferences. Candidate ranking may use protein density and future curated fields such as minimally processed, estimated cost tier, or prep-time tier. Ranking is never a substitute for compatibility filtering.

### Empty coverage response

When no candidates remain, return a clear actionable error identifying the unmet catalogue coverage without asking users to remove an allergy. Example:

> No reviewed catalogue foods currently meet all saved meal-plan requirements: milk allergy, vegetarian preference, and halal restriction. Your allergy remains protected. Add reviewed compatible foods to the nutrition catalogue or update only preferences/restrictions you no longer want applied.

The API error contract and frontend message should preserve this explanation without exposing internal classifier prompts, credentials, or hidden review notes.

## Rollout

### Phase 1: Safe minimum viable coverage

1. Add migration and repository methods.
2. Implement the shared compatibility policy and strict normalization mappings.
3. Seed reviewed, compatible, single-ingredient foods sufficient for the initial Vegetarian + Halal + Milk allergy regression case and establish coverage reporting for every predefined strict option.
4. Apply filtering to fallback, LLM browse, submission, and confirmation paths.
5. Add the coverage-specific error.
6. Keep all non-reviewed cached foods excluded from profiles with an allergy or strict constraint.

### Phase 2: Batch classification and review queue

1. Add the classification schema, policy versioning, and batch script.
2. Run against the cache in dry-run mode.
3. Review reports and approve only supported records.
4. Re-run safely and incrementally as cache data changes.
5. Monitor classification failures, review queue size, candidate coverage, and empty-catalogue errors.

### Phase 3: Broader verified coverage

1. Add authoritative ingredient, manufacturer, and certification data sources where permitted.
2. Add reviewed composite foods and branded food handling.
3. Add controlled administration/review UI if the JSON/CSV workflow is no longer sufficient.
4. Add separately specified policies for sodium, low-FODMAP, cost, preparation time, and other preference options.

## Test Plan

### Migration and repository tests

- Migration is idempotent under the existing Nutrition Agent migration runner.
- Compatibility rows require a valid `nutrition_food_cache` record and are removed on cache-row deletion.
- Check constraints reject invalid lifecycle, confidence, processing, and compatibility statuses.
- Repository queries correctly join cache and compatibility records without cross-user concerns.

### Compatibility-policy tests

- A known milk-containing food is rejected for a milk allergy.
- Unknown allergen metadata is rejected for any declared allergy.
- A reviewed known milk-free food is accepted for a milk allergy.
- Vegetarian rejects meat and fish marked unsuitable.
- Halal rejects non-halal and unknown-halal items.
- The documented `unprocessed_whole_food_v1` policy may mark reviewed raw tomatoes, raw potatoes, and plain water suitable for halal/kosher meal planning without describing them as certified.
- Commercial hummus, canned or seasoned vegetables, tofu without separately reviewed evidence, and other packaged, prepared, or ambiguous foods do not qualify for the whole-food policy and remain `unknown` or `review_required`.
- API, LLM, and UI text never represent a preliminary whole-food planning label as halal or kosher certification.
- A reviewed lentil, rice, or vegetable record is accepted for Vegetarian + Halal + Milk allergy.
- Dairy, meat, pork, alcohol, and incompatible metadata are excluded as appropriate.
- Existing USDA ethyl-alcohol detection remains enforced.
- Unknown custom values remain advisory until a defined strict policy is added.

### Enrichment-command tests

- Dry run performs no writes.
- Apply mode writes valid, versioned, auditable upserts.
- Invalid LLM JSON and invalid schema values are rejected and reported.
- Low-confidence, prepared, branded, and ambiguous records become `review_required`.
- Resume and unchanged-input behaviour is deterministic.
- The command never auto-certifies halal, kosher, gluten-free, or allergen cross-contact safety.

### Generator and API tests

- Deterministic fallback only selects IDs passing the shared function.
- LLM browse returns only IDs passing the shared function.
- Submission and confirmation reject an ID that is later incompatible or unreviewed.
- The profile Vegetarian + Halal + Milk allergy produces a plan when compatible curated foods exist.
- The same profile receives the actionable coverage error when they do not exist.
- Frontend messaging is tested and `npm run build` is run if UI error handling changes.

### Required validation commands

Use the repository-local interpreter on Windows:

```powershell
.venv\Scripts\python.exe -m pytest services/nutrition_agent/tests -q
.venv\Scripts\python.exe -m pytest tests/test_nutrition_routes.py tests/test_nutrition_profile_repository.py -q
```

Run targeted new tests as they are added. Run the frontend build only when frontend code changes:

```powershell
Set-Location frontend; npm run build
```

Also run the project formatter/linter commands already used by the Nutrition Agent changes and `git diff --check` before completion.

## Acceptance Criteria

The implementation is complete when:

1. Meal-plan selection uses persisted compatibility metadata rather than food-name inference.
2. A declared allergy fails closed for unknown or conflicting allergen information.
3. Vegetarian and halal are deterministically enforced for automatic plans.
4. The LLM sees and can submit only compatibility-filtered cached food IDs.
5. The deterministic fallback and all later validation paths use the same policy function.
6. A small, reviewed catalogue can generate a safe plan for Vegetarian + Halal + Milk allergy, while the same cumulative policy applies to all supported allergy/preference/restriction combinations.
7. Missing coverage gives an actionable message while preserving the allergy safeguard.
8. Every automated classification is traceable to a model/policy version and review state.
9. Tests demonstrate compatible inclusion, incompatible exclusion, unknown-data exclusion, and empty-coverage handling.