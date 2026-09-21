-- Persistent, user-owned nutrition tracking.
CREATE TABLE IF NOT EXISTS systemdb.nutrition_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES systemdb.users(id) ON DELETE CASCADE,
    sex_for_energy_equation VARCHAR(16) NOT NULL,
    activity_level VARCHAR(32) NOT NULL,
    nutrition_goal VARCHAR(32) NOT NULL,
    dietary_preferences JSONB NOT NULL DEFAULT '[]'::jsonb,
    dietary_restrictions JSONB NOT NULL DEFAULT '[]'::jsonb,
    allergies JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT nutrition_profile_sex_valid CHECK (sex_for_energy_equation IN ('female', 'male')),
    CONSTRAINT nutrition_profile_activity_valid CHECK (activity_level IN ('sedentary', 'light', 'moderate', 'very_active', 'extra_active')),
    CONSTRAINT nutrition_profile_goal_valid CHECK (nutrition_goal IN ('maintenance', 'fat_loss', 'muscle_gain', 'performance'))
);

CREATE TABLE IF NOT EXISTS systemdb.nutrition_target_snapshots (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
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
CREATE UNIQUE INDEX IF NOT EXISTS nutrition_one_open_target_per_user ON systemdb.nutrition_target_snapshots(user_id) WHERE effective_to IS NULL;

CREATE TABLE IF NOT EXISTS systemdb.nutrition_meals (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    eaten_at TIMESTAMPTZ NOT NULL,
    meal_type VARCHAR(16) NOT NULL,
    notes TEXT,
    source VARCHAR(32) NOT NULL DEFAULT 'manual',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT nutrition_meal_type_valid CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack'))
);
CREATE INDEX IF NOT EXISTS nutrition_meals_user_eaten ON systemdb.nutrition_meals(user_id, eaten_at DESC);

CREATE TABLE IF NOT EXISTS systemdb.nutrition_meal_items (
    id BIGSERIAL PRIMARY KEY,
    meal_id BIGINT NOT NULL REFERENCES systemdb.nutrition_meals(id) ON DELETE CASCADE,
    food_name VARCHAR(255) NOT NULL,
    quantity NUMERIC(9,2) NOT NULL,
    unit VARCHAR(32) NOT NULL,
    grams NUMERIC(9,2),
    calories NUMERIC(9,2) NOT NULL,
    protein_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    carbohydrate_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    fat_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    fiber_g NUMERIC(9,2) NOT NULL DEFAULT 0,
    source VARCHAR(32) NOT NULL DEFAULT 'manual_estimate',
    CONSTRAINT nutrition_item_source_valid CHECK (source IN ('usda', 'manual_estimate', 'meal_plan'))
);