-- Migration 006: Remove application user roles.
-- Existing databases may still have the legacy role check constraint, so drop
-- the column with its dependent default and constraint in one idempotent step.

ALTER TABLE systemdb.users DROP COLUMN IF EXISTS role;