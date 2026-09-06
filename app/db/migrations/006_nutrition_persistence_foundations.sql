-- Migration 006: Nutrition persistence foundations
-- Forward-only additions to the immutable 000-005 baseline.

-- Explicit, versioned nutrition targets. The target-save workflow closes a
-- prior version before inserting the next one; one user cannot have two
-- versions beginning on the same date.
CREATE TABLE systemdb.nutrition_targets (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    inputs JSONB NOT NULL,
    recommended_calories INTEGER NOT NULL CHECK (recommended_calories > 0),
    macro_targets JSONB NOT NULL,
    policy_version VARCHAR(64) NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    UNIQUE (user_id, effective_from)
);

CREATE INDEX idx_nutrition_targets_user_effective
    ON systemdb.nutrition_targets(user_id, effective_from DESC);

-- Timestamps support meal-log history retrieval and future update workflows.
ALTER TABLE systemdb.meal_logs
    ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX idx_meal_logs_user_logged_at_id
    ON systemdb.meal_logs(user_id, logged_at DESC, id DESC);

-- Cache refresh and transient upstream-failure suppression metadata. Existing
-- seeded records remain valid cache entries with their legacy last_updated.
ALTER TABLE systemdb.food_cache
    ADD COLUMN fetched_at TIMESTAMPTZ,
    ADD COLUMN refresh_after TIMESTAMPTZ,
    ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'legacy_seed',
    ADD COLUMN suppression_until TIMESTAMPTZ;

UPDATE systemdb.food_cache
SET fetched_at = last_updated,
    refresh_after = last_updated
WHERE fetched_at IS NULL;

CREATE INDEX idx_food_cache_refresh_after
    ON systemdb.food_cache(refresh_after)
    WHERE refresh_after IS NOT NULL;

CREATE INDEX idx_food_cache_name_ci
    ON systemdb.food_cache(lower(name), fdc_id);

-- The legacy response/tool trace columns are retained for compatibility.
-- Dedicated history presentation is added by forward migration 007.
ALTER TABLE systemdb.nutrition_assessments
    ADD COLUMN policy_version VARCHAR(64),
    ADD COLUMN trigger_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN safety_projection JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN target_summary JSONB,
    ADD COLUMN recommendations JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX idx_nutrition_assessments_user_created_id
    ON systemdb.nutrition_assessments(user_id, created_at DESC, id DESC);
