-- Migration 007: Dedicated privacy-safe assessment-history presentation.
-- History never reads legacy response or tool-trace JSON fields.
ALTER TABLE systemdb.nutrition_assessments
    ADD COLUMN IF NOT EXISTS presentation_message TEXT NOT NULL DEFAULT '';