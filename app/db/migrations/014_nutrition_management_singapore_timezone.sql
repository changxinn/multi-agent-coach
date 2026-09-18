-- Migration 014: Singapore is the Nutrition Management timezone baseline.
-- Preserve any deliberately selected non-UTC IANA timezone.
ALTER TABLE systemdb.nutrition_profiles
    ALTER COLUMN timezone SET DEFAULT 'Asia/Singapore';

UPDATE systemdb.nutrition_profiles
SET timezone = 'Asia/Singapore'
WHERE timezone = 'UTC';