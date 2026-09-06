-- Migration 010: Persist each Nutrition profile's IANA timezone.
-- UTC safely backfills profiles created before timezone became mandatory.
ALTER TABLE systemdb.nutrition_profiles
    ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'UTC';