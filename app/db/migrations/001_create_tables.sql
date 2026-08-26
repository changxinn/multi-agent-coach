-- Migration 001: Create fitness profiles table
-- Idempotent: Safe to run multiple times

-- ===========================================
-- Fitness Profiles Table
-- ===========================================
-- Links to existing systemdb.users table
-- Stores fitness-related user data

CREATE TABLE IF NOT EXISTS systemdb.user_fitness_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES systemdb.users(id) ON DELETE CASCADE,
    fitness_goal VARCHAR(255) DEFAULT 'general fitness',
    fitness_level VARCHAR(50) DEFAULT 'beginner',
    weight_kg NUMERIC(5,2),
    height_cm NUMERIC(5,2),
    age INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id 
ON systemdb.user_fitness_profiles(user_id);

-- Comment for documentation
COMMENT ON TABLE systemdb.user_fitness_profiles IS 
'Fitness profile data for users (goals, measurements, level)';

COMMENT ON COLUMN systemdb.user_fitness_profiles.fitness_level IS 
'Fitness level: beginner, intermediate, advanced';
