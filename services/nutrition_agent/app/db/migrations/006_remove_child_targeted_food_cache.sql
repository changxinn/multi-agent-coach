-- The nutrition catalogue is for adult users. Remove child-targeted USDA products
-- from databases seeded before the curated food-cache cleanup.
DELETE FROM nutrition_food_cache
WHERE provider = 'usda'
  AND (
      description ILIKE 'Babyfood,%'
      OR description ILIKE 'Baby Toddler%'
      OR description ILIKE 'Toddler%'
      OR description ILIKE 'Infant formula,%'
      OR description = 'Water, baby'
  );
