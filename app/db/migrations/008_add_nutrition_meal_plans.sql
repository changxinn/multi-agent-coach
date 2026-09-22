-- Versioned, user-owned meal plans and their structured planned meals.
CREATE TABLE IF NOT EXISTS systemdb.nutrition_meal_plans (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    target_snapshot_id BIGINT NOT NULL
        REFERENCES systemdb.nutrition_target_snapshots(id) ON DELETE RESTRICT,
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
    CONSTRAINT nutrition_meal_plan_status_valid
        CHECK (status IN ('draft', 'active', 'superseded', 'archived')),
    CONSTRAINT nutrition_meal_plan_user_range_version_unique
        UNIQUE (user_id, start_date, end_date, version)
);
CREATE INDEX IF NOT EXISTS nutrition_meal_plans_active_date_idx
    ON systemdb.nutrition_meal_plans (user_id, start_date, end_date, version DESC)
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS systemdb.nutrition_planned_meals (
    id BIGSERIAL PRIMARY KEY,
    meal_plan_id BIGINT NOT NULL
        REFERENCES systemdb.nutrition_meal_plans(id) ON DELETE CASCADE,
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
    CONSTRAINT nutrition_planned_meal_type_valid
        CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    CONSTRAINT nutrition_planned_meal_safety_status_valid
        CHECK (safety_status IN ('safe', 'review_required', 'blocked')),
    CONSTRAINT nutrition_planned_meal_plan_date_type_unique
        UNIQUE (meal_plan_id, planned_date, meal_type)
);
CREATE INDEX IF NOT EXISTS nutrition_planned_meals_plan_date_idx
    ON systemdb.nutrition_planned_meals (meal_plan_id, planned_date, meal_type);

ALTER TABLE systemdb.nutrition_meals
    ADD COLUMN IF NOT EXISTS planned_meal_id BIGINT
    REFERENCES systemdb.nutrition_planned_meals(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS nutrition_meals_planned_meal_idx
    ON systemdb.nutrition_meals(planned_meal_id)
    WHERE planned_meal_id IS NOT NULL;