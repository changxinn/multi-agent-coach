-- Migration 011: PostgreSQL is the canonical durable chat transcript store.
CREATE TABLE systemdb.chat_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(37) NOT NULL UNIQUE CHECK (session_id ~ '^chat_[a-f0-9]{32}$'),
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    history_start_sequence BIGINT NOT NULL DEFAULT 0 CHECK (history_start_sequence >= 0),
    next_sequence BIGINT NOT NULL DEFAULT 1 CHECK (next_sequence > 0),
    summary TEXT,
    summary_through_sequence BIGINT NOT NULL DEFAULT 0 CHECK (summary_through_sequence >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_chat_sessions_user_active_updated
    ON systemdb.chat_sessions(user_id, updated_at DESC)
    WHERE deleted_at IS NULL;

CREATE TABLE systemdb.chat_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES systemdb.chat_sessions(id) ON DELETE CASCADE,
    sequence BIGINT NOT NULL CHECK (sequence > 0),
    role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant')),
    agent_name VARCHAR(100),
    content TEXT NOT NULL CHECK (length(content) > 0 AND octet_length(content) <= 16000),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, sequence),
    CHECK ((role = 'user' AND agent_name IS NULL) OR role = 'assistant')
);

CREATE INDEX idx_chat_messages_session_sequence
    ON systemdb.chat_messages(session_id, sequence);

-- Transcripts are append-only. Clear/delete are represented by controlled
-- session state, preserving prior records for an authorized export/audit path.
CREATE FUNCTION systemdb.prevent_chat_message_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'chat_messages are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER chat_messages_immutable
    BEFORE UPDATE OR DELETE ON systemdb.chat_messages
    FOR EACH ROW EXECUTE FUNCTION systemdb.prevent_chat_message_mutation();