-- One dashboard recommendation per user and UTC calendar day.
CREATE TABLE IF NOT EXISTS systemdb.daily_training_workouts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    workout_date DATE NOT NULL,
    status VARCHAR(32) NOT NULL,
    title VARCHAR(255) NOT NULL,
    workout_text TEXT NOT NULL,
    recovery_note TEXT,
    recovery_status VARCHAR(32) NOT NULL,
    profile_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT daily_training_workout_status_valid CHECK (status IN ('ready', 'recovery_adjusted')),
    CONSTRAINT daily_training_workouts_user_date_unique UNIQUE (user_id, workout_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_training_workouts_user_date
    ON systemdb.daily_training_workouts(user_id, workout_date DESC);