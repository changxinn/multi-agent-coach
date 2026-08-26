-- Manual setup script for database
-- Run this directly in psql if migrations fail

-- ===========================================
-- Step 1: Connect to systemdb database
-- ===========================================
-- \c systemdb

-- ===========================================
-- Step 2: Create schema (if using custom schema)
-- ===========================================
CREATE SCHEMA IF NOT EXISTS systemdb;

-- ===========================================
-- Step 3: Create users table (if not exists)
-- ===========================================
CREATE TABLE IF NOT EXISTS systemdb.users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'USER' 
        CHECK (role IN ('ADMIN', 'STAFF', 'USER')),
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on email
CREATE INDEX IF NOT EXISTS idx_users_email ON systemdb.users(email);

-- ===========================================
-- Step 4: Create fitness profiles table
-- ===========================================
CREATE TABLE IF NOT EXISTS systemdb.user_fitness_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES systemdb.users(id) ON DELETE CASCADE,
    fitness_goal VARCHAR(255) DEFAULT 'general fitness',
    fitness_level VARCHAR(50) DEFAULT 'beginner',
    weight_kg NUMERIC(5,2),
    height_cm NUMERIC(5,2),
    age INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id 
ON systemdb.user_fitness_profiles(user_id);

-- ===========================================
-- Step 5: Grant permissions
-- ===========================================
GRANT ALL PRIVILEGES ON SCHEMA systemdb TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA systemdb TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA systemdb TO postgres;
