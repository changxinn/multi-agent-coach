CREATE TABLE IF NOT EXISTS exercises (
    id BIGSERIAL PRIMARY KEY, name VARCHAR(128) UNIQUE NOT NULL, aliases TEXT[] NOT NULL DEFAULT '{}',
    guidance TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS training_programs (
    id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, version INTEGER NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'active',
    goal VARCHAR(128) NOT NULL, program JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, version)
);
CREATE TABLE IF NOT EXISTS workout_logs (
    id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, idempotency_key VARCHAR(128) NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL, rpe NUMERIC(3,1), metadata JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, idempotency_key)
);
CREATE TABLE IF NOT EXISTS daily_recommendations (
    id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, workout_date DATE NOT NULL, status VARCHAR(32) NOT NULL, title VARCHAR(255) NOT NULL,
    workout_text TEXT NOT NULL, recovery_note TEXT, recovery_status VARCHAR(32) NOT NULL, profile_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, workout_date)
);
CREATE TABLE IF NOT EXISTS training_adaptations (
    id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, from_program_id BIGINT, to_program_id BIGINT,
    reason TEXT NOT NULL, details JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO exercises (name, aliases, guidance) VALUES
('squat', ARRAY['goblet squat'], 'Keep your chest tall, brace your trunk, let knees track over toes, and use a pain-free depth.'),
('deadlift', ARRAY['romanian deadlift','rdl'], 'Hinge at the hips with a neutral spine, keep the load close, and stop if form changes.'),
('push-up', ARRAY['press-up'], 'Keep a straight line from head to heels, lower under control, and use an incline to scale.'),
('row', ARRAY['dumbbell row','barbell row'], 'Brace the torso, pull toward lower ribs, and avoid shrugging.')
ON CONFLICT (name) DO NOTHING;