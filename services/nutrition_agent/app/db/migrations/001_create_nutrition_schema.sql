-- Nutrition Agent-private data. user_id is an externally owned identifier;
-- no cross-database foreign key to the main application's users table exists.
CREATE TABLE IF NOT EXISTS nutrition_target_snapshots (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    bmr_kcal INTEGER NOT NULL,
    tdee_kcal INTEGER NOT NULL,
    calorie_target_kcal INTEGER NOT NULL,
    protein_target_g NUMERIC(7,2) NOT NULL,
    carbohydrate_target_g NUMERIC(7,2) NOT NULL,
    fat_target_g NUMERIC(7,2) NOT NULL,
    fiber_target_g NUMERIC(7,2) NOT NULL,
    calculation_method VARCHAR(64) NOT NULL,
    calculation_inputs JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT nutrition_target_dates_valid CHECK (effective_to IS NULL OR effective_to >= effective_from)
);
CREATE UNIQUE INDEX IF NOT EXISTS nutrition_one_open_target_per_user ON nutrition_target_snapshots(user_id) WHERE effective_to IS NULL;

CREATE TABLE IF NOT EXISTS nutrition_food_cache (
    id BIGSERIAL PRIMARY KEY,
    provider VARCHAR(32) NOT NULL,
    provider_food_id VARCHAR(64) NOT NULL,
    description VARCHAR(512) NOT NULL,
    serving_size_g NUMERIC(9,2),
    serving_description VARCHAR(255),
    calories_per_100g NUMERIC(9,2),
    protein_g_per_100g NUMERIC(9,2),
    carbohydrate_g_per_100g NUMERIC(9,2),
    fat_g_per_100g NUMERIC(9,2),
    fiber_g_per_100g NUMERIC(9,2),
    allergen_data JSONB,
    allergen_status VARCHAR(16) NOT NULL DEFAULT 'unknown',
    raw_response JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT nutrition_food_cache_provider_unique UNIQUE (provider, provider_food_id),
    CONSTRAINT nutrition_food_cache_allergen_status_valid CHECK (allergen_status IN ('known', 'unknown'))
);
CREATE INDEX IF NOT EXISTS nutrition_food_cache_catalogue_idx ON nutrition_food_cache(provider, description, id)
    WHERE calories_per_100g IS NOT NULL AND protein_g_per_100g IS NOT NULL
      AND carbohydrate_g_per_100g IS NOT NULL AND fat_g_per_100g IS NOT NULL;

CREATE TABLE IF NOT EXISTS nutrition_idempotency_keys (
    user_id BIGINT NOT NULL,
    operation VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL,
    request_fingerprint VARCHAR(64) NOT NULL,
    response JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, operation, idempotency_key)
);

CREATE TABLE IF NOT EXISTS nutrition_meal_plans (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    target_snapshot_id BIGINT NOT NULL REFERENCES nutrition_target_snapshots(id) ON DELETE RESTRICT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    version INTEGER NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'draft',
    generated_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
    safety_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT nutrition_meal_plan_dates_valid CHECK (end_date >= start_date),
    CONSTRAINT nutrition_meal_plan_version_valid CHECK (version > 0),
    CONSTRAINT nutrition_meal_plan_status_valid CHECK (status IN ('draft', 'active', 'superseded', 'archived')),
    CONSTRAINT nutrition_meal_plan_user_range_version_unique UNIQUE (user_id, start_date, end_date, version)
);
CREATE INDEX IF NOT EXISTS nutrition_meal_plans_active_date_idx ON nutrition_meal_plans(user_id, start_date, end_date, version DESC) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS nutrition_planned_meals (
    id BIGSERIAL PRIMARY KEY,
    meal_plan_id BIGINT NOT NULL REFERENCES nutrition_meal_plans(id) ON DELETE CASCADE,
    planned_date DATE NOT NULL,
    meal_type VARCHAR(16) NOT NULL,
    calorie_target_kcal NUMERIC(9,2) NOT NULL DEFAULT 0,
    protein_target_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    carbohydrate_target_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    fat_target_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    fiber_target_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    items JSONB NOT NULL DEFAULT '[]'::jsonb,
    safety_status VARCHAR(16) NOT NULL DEFAULT 'review_required',
    safety_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT nutrition_planned_meal_type_valid CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    CONSTRAINT nutrition_planned_meal_safety_status_valid CHECK (safety_status IN ('safe', 'review_required', 'blocked')),
    CONSTRAINT nutrition_planned_meal_plan_date_type_unique UNIQUE (meal_plan_id, planned_date, meal_type)
);