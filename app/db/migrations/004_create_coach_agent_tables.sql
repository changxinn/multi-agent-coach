-- Migration 004: Head Coach routing events and summarizer output

CREATE TABLE IF NOT EXISTS systemdb.head_coach_routing_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    session_id VARCHAR(64),
    next_agent VARCHAR(64) NOT NULL,
    routing_reason TEXT,
    needs_clarification BOOLEAN NOT NULL DEFAULT false,
    safety_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    user_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_head_coach_routing_user_created
    ON systemdb.head_coach_routing_events(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS systemdb.coach_summaries (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    session_id VARCHAR(64),
    summary_type VARCHAR(32) NOT NULL,
    summary_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_coach_summaries_user_created
    ON systemdb.coach_summaries(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_coach_summaries_type_created
    ON systemdb.coach_summaries(summary_type, created_at DESC);
