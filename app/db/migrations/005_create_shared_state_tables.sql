-- Shared, main-application state. This database is the canonical source for
-- user identity, cross-agent preferences, workout progress, meal history,
-- sleep history, and conversation history.

ALTER TABLE systemdb.user_fitness_profiles
    ADD COLUMN IF NOT EXISTS sex_for_energy_equation VARCHAR(16),
    ADD COLUMN IF NOT EXISTS activity_level VARCHAR(32),
    ADD COLUMN IF NOT EXISTS nutrition_goal VARCHAR(32),
    ADD COLUMN IF NOT EXISTS dietary_preferences JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS dietary_restrictions JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS allergies JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS systemdb.nutrition_meals (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    eaten_at TIMESTAMPTZ NOT NULL,
    meal_type VARCHAR(16) NOT NULL,
    notes TEXT,
    source VARCHAR(32) NOT NULL DEFAULT 'nutrition_agent',
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
    -- Catalogue identities are external strings. Nutrition's private cache IDs
    -- are deliberately not persisted in the shared database.
    food_provider VARCHAR(32),
    provider_food_id VARCHAR(64),
    nutrition_snapshot JSONB,
    CONSTRAINT nutrition_item_source_valid CHECK (source IN ('usda', 'manual_estimate', 'meal_plan'))
);
-- Upgrade tables created by the legacy Nutrition migration before creating the
-- provider lookup index below. CREATE TABLE IF NOT EXISTS does not add columns
-- to an existing table.
ALTER TABLE systemdb.nutrition_meal_items
    ADD COLUMN IF NOT EXISTS food_provider VARCHAR(32),
    ADD COLUMN IF NOT EXISTS provider_food_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS nutrition_snapshot JSONB;
CREATE INDEX IF NOT EXISTS nutrition_meal_items_provider_idx
    ON systemdb.nutrition_meal_items(food_provider, provider_food_id);

CREATE TABLE IF NOT EXISTS systemdb.workout_progress (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS workout_progress_user_occurred
    ON systemdb.workout_progress(user_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS systemdb.chat_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS chat_sessions_user_activity
    ON systemdb.chat_sessions(user_id, last_activity DESC);

CREATE TABLE IF NOT EXISTS systemdb.chat_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES systemdb.chat_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    name VARCHAR(255),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS chat_messages_session_created
    ON systemdb.chat_messages(session_id, created_at, id);