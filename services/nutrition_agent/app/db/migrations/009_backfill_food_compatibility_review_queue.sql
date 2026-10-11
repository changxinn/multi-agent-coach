-- Enroll every cached food in compatibility review without replacing curated or human-reviewed records.
-- Backfilled rows require review unless a subsequent deterministic policy classifies them.
INSERT INTO nutrition_food_compatibility (
    food_cache_id,
    review_status,
    evidence,
    classifier_version,
    review_note
)
SELECT
    f.id,
    'review_required',
    jsonb_build_object(
        'source', 'food-cache backfill',
        'scope', 'Existing food-cache item enrolled for compatibility review',
        'certification', 'not evaluated; no certification claim'
    ),
    'compatibility_queue_backfill_v1',
    'Automatically enrolled in compatibility review queue.'
FROM nutrition_food_cache f
ON CONFLICT (food_cache_id) DO NOTHING;
