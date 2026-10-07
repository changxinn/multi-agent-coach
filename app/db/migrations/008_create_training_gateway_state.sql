-- Main API owns athlete preferences and completed-workout history.
CREATE TABLE IF NOT EXISTS systemdb.training_preferences (
    user_id BIGINT PRIMARY KEY REFERENCES systemdb.users(id) ON DELETE CASCADE,
    equipment JSONB NOT NULL DEFAULT '[]'::jsonb,
    training_days_per_week SMALLINT,
    session_duration_minutes SMALLINT,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE systemdb.workout_progress
    ADD COLUMN IF NOT EXISTS duration_minutes SMALLINT,
    ADD COLUMN IF NOT EXISTS session_rpe NUMERIC(3,1),
    ADD COLUMN IF NOT EXISTS notes TEXT,
    ADD COLUMN IF NOT EXISTS exercise_performance JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);
CREATE UNIQUE INDEX IF NOT EXISTS workout_progress_user_idempotency_key
    ON systemdb.workout_progress(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL;