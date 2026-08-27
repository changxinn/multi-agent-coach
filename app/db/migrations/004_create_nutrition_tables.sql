-- Migration 004: Nutrition Agent persistence
-- Idempotent: Safe to run multiple times

-- ===========================================
-- 1. Nutrition Profiles Table
-- ===========================================
CREATE TABLE IF NOT EXISTS systemdb.nutrition_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES systemdb.users(id) ON DELETE CASCADE,
    dietary_preference VARCHAR(50) DEFAULT 'omnivore',
    dietary_restrictions JSONB DEFAULT '[]',
    allergies JSONB DEFAULT '[]',
    meals_per_day INTEGER DEFAULT 3,
    target_calories INTEGER,
    activity_level VARCHAR(20),
    age INTEGER,
    gender VARCHAR(10),
    weight_kg NUMERIC(5,2),
    height_cm NUMERIC(5,2),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_nutrition_profiles_user_id 
ON systemdb.nutrition_profiles(user_id);

COMMENT ON TABLE systemdb.nutrition_profiles IS 
'Nutrition preferences and profile data for users';

COMMENT ON COLUMN systemdb.nutrition_profiles.dietary_preference IS 
'Dietary preference: omnivore, vegetarian, vegan, pescatarian, other';


-- ===========================================
-- 2. Meal Logs Table
-- ===========================================
CREATE TABLE IF NOT EXISTS systemdb.meal_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    meal_type VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    calories INTEGER,
    protein_g NUMERIC(5,2),
    carbs_g NUMERIC(5,2),
    fat_g NUMERIC(5,2),
    logged_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_meal_logs_user_date 
ON systemdb.meal_logs(user_id, logged_at DESC);

COMMENT ON COLUMN systemdb.meal_logs.meal_type IS 
'Meal type: breakfast, lunch, dinner, snack';


-- ===========================================
-- 3. Nutrition Assessments Table
-- ===========================================
CREATE TABLE IF NOT EXISTS systemdb.nutrition_assessments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    status VARCHAR(16) NOT NULL,
    score INTEGER NOT NULL,
    tdee INTEGER,
    macro_targets JSONB,
    response JSONB NOT NULL,
    tool_trace JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_nutrition_assessments_user_created 
ON systemdb.nutrition_assessments(user_id, created_at DESC);

COMMENT ON COLUMN systemdb.nutrition_assessments.status IS 
'Assessment status: green, amber, red, escalate';


-- ===========================================
-- 4. Food Cache Table
-- ===========================================
CREATE TABLE IF NOT EXISTS systemdb.food_cache (
    fdc_id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    brand VARCHAR(255),
    serving_size_g INTEGER,
    calories NUMERIC(8,2),
    protein_g NUMERIC(6,2),
    carbs_g NUMERIC(6,2),
    fat_g NUMERIC(6,2),
    fiber_g NUMERIC(6,2),
    category VARCHAR(50),
    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_food_cache_category 
ON systemdb.food_cache(category);

CREATE INDEX IF NOT EXISTS idx_food_cache_name 
ON systemdb.food_cache(name);

COMMENT ON TABLE systemdb.food_cache IS 
'Local cache of common foods from USDA FoodData Central';
