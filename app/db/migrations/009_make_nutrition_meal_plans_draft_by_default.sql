-- Preserve draft creation semantics for databases where migration 008 was applied.
ALTER TABLE systemdb.nutrition_meal_plans
    ALTER COLUMN status SET DEFAULT 'draft';