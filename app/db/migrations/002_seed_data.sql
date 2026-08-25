-- Migration 002: Seed data
-- Idempotent: Safe to run multiple times
-- Creates default admin user if not exists

-- ===========================================
-- Seed Admin User
-- ===========================================
-- Email: admin@example.com (configurable via env var)
-- Password: ChangeMe123! (configurable via env var)
-- Role: ADMIN

-- Note: This SQL is for reference only.
-- The actual admin user is created by the Python seed script (app/db/seed.py)
-- which uses bcrypt to hash the password from environment variables.

-- The Python script will:
-- 1. Check if admin user exists in public.users table
-- 2. If not, create user with bcrypt-hashed password
-- 3. Create fitness profile in public.user_fitness_profiles
