CREATE TABLE IF NOT EXISTS systemdb.nutrition_idempotency_keys (
    user_id BIGINT NOT NULL REFERENCES systemdb.users(id) ON DELETE CASCADE,
    operation VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL,
    request_fingerprint VARCHAR(64) NOT NULL,
    response JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, operation, idempotency_key)
);
