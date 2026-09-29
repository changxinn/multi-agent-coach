-- System policy: ordered USDA-description rules assign compatibility metadata.
-- Animal-protein rules take precedence over subsequent food-category rules.
WITH classified AS (
    SELECT c.food_cache_id, c.review_status AS prior_review_status,
           CASE
               WHEN f.description ILIKE '%pork%' THEN 'usda_description_contains_pork_v2'
               WHEN f.description ILIKE '%beef%' THEN 'usda_description_contains_beef_no_pork_v1'
               WHEN f.description ILIKE '%lamb%' OR f.description ILIKE '%mutton%' THEN 'usda_description_contains_lamb_mutton_v1'
               WHEN f.description ILIKE '%fish%' THEN 'usda_description_contains_fish_v1'
               WHEN LOWER(f.description) LIKE 'broccoli, raw%' THEN 'usda_raw_broccoli_v1'
               WHEN LOWER(f.description) LIKE 'squash, summer, zucchini%' THEN 'usda_zucchini_v1'
               WHEN LOWER(f.description) LIKE 'blackberr%, raw%' OR LOWER(f.description) LIKE 'strawberr%, raw%' OR LOWER(f.description) LIKE 'blueberr%, raw%' OR LOWER(f.description) LIKE 'banana%, raw%' THEN 'usda_raw_berries_banana_v1'
               WHEN LOWER(f.description) = 'yeast' THEN 'usda_yeast_v1'
               WHEN LOWER(f.description) LIKE 'peanuts,%' THEN 'usda_peanuts_v1'
               WHEN LOWER(f.description) IN ('water, bottled, plain', 'water, bottled, generic', 'water, tap') OR LOWER(f.description) LIKE 'beverages, water, tap%' OR LOWER(f.description) LIKE 'beverages, water, bottled, non-carbonated%' THEN 'usda_plain_water_v1'
               WHEN LOWER(f.description) = 'beverages, whey protein powder isolate' THEN 'usda_whey_protein_isolate_v1'
               WHEN LOWER(f.description) = 'black beans and white rice' THEN 'usda_black_beans_white_rice_v1'
               WHEN LOWER(f.description) = 'vegan mayonnaise' THEN 'usda_vegan_mayonnaise_v1'
               WHEN LOWER(f.description) LIKE 'bread,%' THEN 'usda_bread_v1'
               WHEN LOWER(f.description) LIKE 'waffle%' THEN 'usda_waffle_v1'
               WHEN LOWER(f.description) LIKE 'rice,%' THEN 'usda_rice_v1'
               WHEN LOWER(f.description) LIKE 'beverages, coffee%' THEN 'usda_coffee_v1'
               WHEN LOWER(f.description) LIKE 'tea,%' OR LOWER(f.description) LIKE 'beverages, tea%' THEN 'usda_tea_v1'
           END AS rule,
           f.description ~* '\m(alcoholic|beer|wine|rum|whiskey|whisky|vodka|brandy|liqueur)\M' AS contains_alcohol
    FROM nutrition_food_compatibility c
    JOIN nutrition_food_cache f ON f.id = c.food_cache_id
    WHERE f.provider = 'usda'
), resolved AS (
    SELECT *, CASE
        WHEN rule = 'usda_description_contains_pork_v2' THEN '{"vegetarian":"unsuitable","vegan":"unsuitable","pescatarian":"unsuitable","halal":"unsuitable","kosher":"unsuitable","gluten_free":"suitable","dairy_free":"suitable","egg_free":"suitable","soy_free":"suitable","nut_free":"suitable","no_pork":"unsuitable","no_beef":"suitable","alcohol_free":"suitable"}'::jsonb
        WHEN rule = 'usda_description_contains_beef_no_pork_v1' THEN '{"vegetarian":"unsuitable","vegan":"unsuitable","pescatarian":"unsuitable","halal":"suitable","kosher":"unsuitable","gluten_free":"suitable","dairy_free":"suitable","egg_free":"suitable","soy_free":"suitable","nut_free":"suitable","no_pork":"suitable","no_beef":"unsuitable","alcohol_free":"suitable"}'::jsonb
        WHEN rule = 'usda_description_contains_lamb_mutton_v1' THEN '{"vegetarian":"unsuitable","vegan":"unsuitable","pescatarian":"unsuitable","halal":"suitable","kosher":"unsuitable","gluten_free":"suitable","dairy_free":"suitable","egg_free":"suitable","soy_free":"suitable","nut_free":"suitable","no_pork":"suitable","no_beef":"suitable","alcohol_free":"suitable"}'::jsonb
        WHEN rule = 'usda_description_contains_fish_v1' THEN '{"vegetarian":"unsuitable","vegan":"unsuitable","pescatarian":"suitable","halal":"suitable","kosher":"unsuitable","gluten_free":"suitable","dairy_free":"suitable","egg_free":"suitable","soy_free":"suitable","nut_free":"suitable","no_pork":"suitable","no_beef":"suitable","alcohol_free":"suitable"}'::jsonb
        WHEN rule = 'usda_peanuts_v1' THEN '{"vegetarian":"suitable","vegan":"suitable","pescatarian":"suitable","halal":"suitable","kosher":"suitable","gluten_free":"suitable","dairy_free":"suitable","egg_free":"suitable","soy_free":"suitable","nut_free":"unsuitable","no_pork":"suitable","no_beef":"suitable","alcohol_free":"suitable"}'::jsonb
        WHEN rule = 'usda_whey_protein_isolate_v1' THEN '{"vegetarian":"suitable","vegan":"unsuitable","pescatarian":"suitable","halal":"suitable","kosher":"suitable","gluten_free":"suitable","dairy_free":"unsuitable","egg_free":"suitable","soy_free":"suitable","nut_free":"suitable","no_pork":"suitable","no_beef":"suitable","alcohol_free":"suitable"}'::jsonb
        WHEN contains_alcohol THEN '{"vegetarian":"suitable","vegan":"suitable","pescatarian":"suitable","halal":"suitable","kosher":"suitable","gluten_free":"suitable","dairy_free":"suitable","egg_free":"suitable","soy_free":"suitable","nut_free":"suitable","no_pork":"suitable","no_beef":"suitable","alcohol_free":"unsuitable"}'::jsonb
        ELSE '{"vegetarian":"suitable","vegan":"suitable","pescatarian":"suitable","halal":"suitable","kosher":"suitable","gluten_free":"suitable","dairy_free":"suitable","egg_free":"suitable","soy_free":"suitable","nut_free":"suitable","no_pork":"suitable","no_beef":"suitable","alcohol_free":"suitable"}'::jsonb
    END AS strict_suitability
    FROM classified WHERE rule IS NOT NULL
), candidates AS (
    SELECT * FROM resolved
    WHERE (prior_review_status <> 'approved' OR EXISTS (
        SELECT 1 FROM nutrition_food_compatibility c
        WHERE c.food_cache_id = resolved.food_cache_id
          AND c.evidence #>> '{system_triage,rule}' LIKE 'usda_description_contains_%_v1'
    ))
      AND NOT EXISTS (
          SELECT 1 FROM nutrition_food_compatibility c
          WHERE c.food_cache_id = resolved.food_cache_id
            AND c.evidence #>> '{system_triage,rule}' = resolved.rule
      )
), updated AS (
    UPDATE nutrition_food_compatibility c
    SET review_status = 'approved', allergen_status = 'known', known_allergens = '[]'::jsonb,
        strict_suitability = candidates.strict_suitability,
        evidence = c.evidence || jsonb_build_object('system_triage', jsonb_build_object(
            'rule', candidates.rule, 'source', 'USDA FoodData Central description',
            'scope', 'system policy: ordered food compatibility rules',
            'confidence_basis', 'policy-assigned confidence; description match is case-insensitive')),
        confidence = 0.500, classifier_version = 'system_food_compatibility_policy_v1',
        review_note = 'System compatibility policy: ordered USDA food description rule.',
        reviewer_user_id = 0, reviewer_email = 'system@nutrition-agent.local',
        reviewed_by = 'system@nutrition-agent.local', reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
    FROM candidates WHERE c.food_cache_id = candidates.food_cache_id
    RETURNING c.food_cache_id, candidates.prior_review_status, c.review_status, c.allergen_status,
              c.known_allergens, c.strict_suitability, c.evidence, c.confidence,
              c.classifier_version, c.policy_version, c.review_note
)
INSERT INTO nutrition_food_compatibility_review_history (
    food_cache_id, prior_review_status, result_review_status, metadata_snapshot,
    reviewer_user_id, reviewer_email, review_note
)
SELECT food_cache_id, prior_review_status, review_status,
       jsonb_build_object('allergen_status', allergen_status, 'known_allergens', known_allergens,
           'strict_suitability', strict_suitability, 'evidence', evidence, 'confidence', confidence,
           'classifier_version', classifier_version, 'policy_version', policy_version),
       0, 'system@nutrition-agent.local', review_note
FROM updated;