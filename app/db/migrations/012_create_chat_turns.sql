-- Migration 012: durable request idempotency for chat turns.
CREATE TABLE systemdb.chat_turns (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES systemdb.chat_sessions(id) ON DELETE CASCADE,
    idempotency_key UUID NOT NULL,
    request_fingerprint CHAR(64) NOT NULL CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
    status VARCHAR(16) NOT NULL CHECK (status IN ('processing', 'completed', 'failed')),
    response_text TEXT,
    response_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    UNIQUE(session_id, idempotency_key),
    CHECK (
        (status = 'completed' AND response_text IS NOT NULL AND completed_at IS NOT NULL)
        OR status IN ('processing', 'failed')
    )
);

CREATE INDEX idx_chat_turns_session_status
    ON systemdb.chat_turns(session_id, status);