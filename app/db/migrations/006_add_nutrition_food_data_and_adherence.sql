-- Food provider cache and materialized daily nutrition adherence.
CREATE TABLE IF NOT EXISTS systemdb.nutrition_food_cache (
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
    CONSTRAINT nutrition_food_cache_allergen_status_valid
        CHECK (allergen_status IN ('known', 'unknown'))
);
CREATE INDEX IF NOT EXISTS nutrition_food_cache_description_idx
    ON systemdb.nutrition_food_cache (provider, description);
CREATE INDEX IF NOT EXISTS nutrition_food_cache_catalogue_idx
    ON systemdb.nutrition_food_cache (provider, description, id)
    WHERE calories_per_100g IS NOT NULL
      AND protein_g_per_100g IS NOT NULL
      AND carbohydrate_g_per_100g IS NOT NULL
      AND fat_g_per_100g IS NOT NULL;

ALTER TABLE systemdb.nutrition_meal_items
    ADD COLUMN IF NOT EXISTS food_cache_id BIGINT
    REFERENCES systemdb.nutrition_food_cache(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS nutrition_meal_items_food_cache_idx
    ON systemdb.nutrition_meal_items(food_cache_id);

CREATE TABLE IF NOT EXISTS systemdb.nutrition_daily_summaries (
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    summary_date DATE NOT NULL,
    target_snapshot_id BIGINT REFERENCES systemdb.nutrition_target_snapshots(id)
        ON DELETE SET NULL,
    calories NUMERIC(9,2) NOT NULL DEFAULT 0,
    protein_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    carbohydrate_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    fat_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    fiber_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    meal_count INTEGER NOT NULL DEFAULT 0,
    calorie_adherence_pct NUMERIC(7,2),
    protein_adherence_pct NUMERIC(7,2),
    plan_adherence_pct NUMERIC(7,2),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, summary_date)
);