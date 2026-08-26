-- Migration 003: Recovery Agent persistence

CREATE TABLE IF NOT EXISTS systemdb.sleep_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes BETWEEN 0 AND 1440),
    quality INTEGER NOT NULL CHECK (quality BETWEEN 1 AND 5),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS systemdb.recovery_checkins (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    energy INTEGER NOT NULL CHECK (energy BETWEEN 1 AND 10),
    soreness INTEGER NOT NULL CHECK (soreness BETWEEN 1 AND 10),
    stress INTEGER NOT NULL CHECK (stress BETWEEN 1 AND 10),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS systemdb.recovery_assessments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    status VARCHAR(16) NOT NULL,
    score INTEGER NOT NULL,
    response JSONB NOT NULL,
    tool_trace JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sleep_logs_user_created ON systemdb.sleep_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recovery_checkins_user_created ON systemdb.recovery_checkins(user_id, created_at DESC);
