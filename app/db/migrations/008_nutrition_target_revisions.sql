-- Migration 008: Immutable revisions for target replacements sharing a date.
-- Date-only effective periods cannot represent ordering within one calendar day,
-- so a monotonic revision selects the replacement deterministically.
ALTER TABLE systemdb.nutrition_targets
    ADD COLUMN version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0);

ALTER TABLE systemdb.nutrition_targets
    DROP CONSTRAINT nutrition_targets_user_id_effective_from_key,
    ADD CONSTRAINT nutrition_targets_user_id_effective_from_version_key
        UNIQUE (user_id, effective_from, version);

CREATE INDEX idx_nutrition_targets_current_revision
    ON systemdb.nutrition_targets(user_id, effective_from DESC, version DESC);