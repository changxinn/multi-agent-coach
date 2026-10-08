-- Training Agent is the canonical owner of training-domain user state.
CREATE TABLE IF NOT EXISTS athlete_training_profiles (
    user_id BIGINT PRIMARY KEY,
    fitness_goal VARCHAR(255) NOT NULL DEFAULT 'general fitness',
    fitness_level VARCHAR(50) NOT NULL DEFAULT 'beginner',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS training_preferences (
    user_id BIGINT PRIMARY KEY,
    equipment JSONB NOT NULL DEFAULT '[]'::jsonb,
    training_days_per_week SMALLINT,
    session_duration_minutes SMALLINT,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- workout_logs was created by the initial Training Agent scaffold. It is now
-- the authoritative canonical workout history for this bounded context.
ALTER TABLE workout_logs
    ADD COLUMN IF NOT EXISTS duration_minutes SMALLINT,
    ADD COLUMN IF NOT EXISTS session_rpe NUMERIC(3,1),
    ADD COLUMN IF NOT EXISTS notes TEXT,
    ADD COLUMN IF NOT EXISTS exercise_performance JSONB NOT NULL DEFAULT '[]'::jsonb;