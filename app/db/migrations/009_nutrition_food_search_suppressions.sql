-- Migration 009: query-level USDA search suppression for transient failures/no results.
CREATE TABLE systemdb.food_search_suppressions (
    normalized_query VARCHAR(100) PRIMARY KEY,
    suppression_until TIMESTAMPTZ NOT NULL,
    reason VARCHAR(32) NOT NULL CHECK (reason IN ('no_result', 'unavailable')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
