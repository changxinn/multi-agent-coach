-- Application-owned compatibility metadata, initial reviewed seed, enrichment support, and review audit history.
-- USDA cache data remains unchanged. Every statement is safe to rerun at Nutrition Agent startup.
CREATE TABLE IF NOT EXISTS nutrition_food_compatibility (
    food_cache_id BIGINT PRIMARY KEY REFERENCES nutrition_food_cache(id) ON DELETE CASCADE,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'approved', 'rejected', 'needs_review')),
    allergen_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (allergen_status IN ('unknown', 'known', 'conflicting')),
    known_allergens JSONB NOT NULL DEFAULT '[]'::jsonb,
    strict_suitability JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence NUMERIC(4,3),
    classifier_version TEXT,
    policy_version TEXT NOT NULL DEFAULT 'unprocessed_whole_food_v1',
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CHECK (jsonb_typeof(known_allergens) = 'array'),
    CHECK (jsonb_typeof(strict_suitability) = 'object'),
    CHECK (jsonb_typeof(evidence) = 'object')
);

CREATE INDEX IF NOT EXISTS ix_nutrition_food_compatibility_approved
    ON nutrition_food_compatibility (review_status)
    WHERE review_status = 'approved';

INSERT INTO nutrition_food_compatibility (
    food_cache_id, review_status, allergen_status, known_allergens,
    strict_suitability, evidence, confidence, classifier_version, policy_version,
    reviewed_by, reviewed_at
)
SELECT id, 'approved', 'known', '[]'::jsonb,
       '{"vegetarian":"suitable","vegan":"suitable","pescatarian":"suitable","halal":"suitable","kosher":"suitable","gluten_free":"suitable","dairy_free":"suitable","egg_free":"suitable","soy_free":"suitable","nut_free":"suitable","no_pork":"suitable","no_beef":"suitable","alcohol_free":"suitable"}'::jsonb,
       '{"source":"USDA FoodData Central description","scope":"reviewed raw unambiguous single-ingredient plant food","certification":"not a halal or kosher certification"}'::jsonb,
       1.000, 'manual_seed_v1', 'unprocessed_whole_food_v1', 'system_seed', CURRENT_TIMESTAMP
FROM nutrition_food_cache
WHERE provider = 'usda'
  AND provider_food_id IN (
      '321360', '323505', '325430', '746769', '746770', '747447',
      '790577', '790646', '1104647', '1104962', '1105073', '1105314'
  )
  AND description ILIKE '%raw%'
  AND description NOT ILIKE '%frozen%'
ON CONFLICT (food_cache_id) DO NOTHING;

ALTER TABLE nutrition_food_compatibility
    ADD COLUMN IF NOT EXISTS input_fingerprint TEXT;

ALTER TABLE nutrition_food_compatibility
    DROP CONSTRAINT IF EXISTS nutrition_food_compatibility_review_status_check;

ALTER TABLE nutrition_food_compatibility
    ADD CONSTRAINT nutrition_food_compatibility_review_status_check
    CHECK (
        review_status IN (
            'pending', 'auto_classified', 'approved', 'rejected',
            'needs_review', 'review_required'
        )
    );

CREATE INDEX IF NOT EXISTS ix_nutrition_food_compatibility_fingerprint
    ON nutrition_food_compatibility (input_fingerprint)
    WHERE input_fingerprint IS NOT NULL;

ALTER TABLE nutrition_food_compatibility
    ADD COLUMN IF NOT EXISTS review_note TEXT;

ALTER TABLE nutrition_food_compatibility
    ADD COLUMN IF NOT EXISTS reviewer_user_id BIGINT;

ALTER TABLE nutrition_food_compatibility
    ADD COLUMN IF NOT EXISTS reviewer_email TEXT;

CREATE TABLE IF NOT EXISTS nutrition_food_compatibility_review_history (
    id BIGSERIAL PRIMARY KEY,
    food_cache_id BIGINT NOT NULL REFERENCES nutrition_food_cache(id) ON DELETE CASCADE,
    prior_review_status TEXT,
    result_review_status TEXT NOT NULL,
    metadata_snapshot JSONB NOT NULL,
    reviewer_user_id BIGINT NOT NULL,
    reviewer_email TEXT NOT NULL,
    review_note TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (jsonb_typeof(metadata_snapshot) = 'object')
);

CREATE INDEX IF NOT EXISTS ix_nutrition_food_compatibility_review_queue
    ON nutrition_food_compatibility (review_status, updated_at DESC, food_cache_id);

CREATE INDEX IF NOT EXISTS ix_nutrition_food_compatibility_review_history_food
    ON nutrition_food_compatibility_review_history (food_cache_id, reviewed_at DESC, id DESC);