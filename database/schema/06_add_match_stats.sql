-- ============================================================================
-- File: 06_add_match_stats.sql
-- Description: Adds shot/corner/foul/card columns to pl_data.matches
-- Run AFTER the initial schema (01-05) if upgrading an existing DB.
-- Safe to re-run (uses IF NOT EXISTS).
-- ============================================================================

SET search_path TO pl_data, public;

-- Add shots columns
ALTER TABLE pl_data.matches
    ADD COLUMN IF NOT EXISTS shots_for               INTEGER,
    ADD COLUMN IF NOT EXISTS shots_against           INTEGER,
    ADD COLUMN IF NOT EXISTS shots_on_target_for     INTEGER,
    ADD COLUMN IF NOT EXISTS shots_on_target_against INTEGER,
    ADD COLUMN IF NOT EXISTS corners_for             INTEGER,
    ADD COLUMN IF NOT EXISTS corners_against         INTEGER,
    ADD COLUMN IF NOT EXISTS fouls_for               INTEGER,
    ADD COLUMN IF NOT EXISTS fouls_against           INTEGER,
    ADD COLUMN IF NOT EXISTS yellow_cards            INTEGER,
    ADD COLUMN IF NOT EXISTS red_cards               INTEGER;

-- Add CHECK constraints for new columns (only if they don't exist)
DO $$
BEGIN
    -- Shots non-negative
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_shots_for'
    ) THEN
        ALTER TABLE pl_data.matches
            ADD CONSTRAINT check_shots_for CHECK (shots_for IS NULL OR shots_for >= 0),
            ADD CONSTRAINT check_shots_against CHECK (shots_against IS NULL OR shots_against >= 0),
            ADD CONSTRAINT check_sot_for CHECK (shots_on_target_for IS NULL OR shots_on_target_for >= 0),
            ADD CONSTRAINT check_sot_against CHECK (shots_on_target_against IS NULL OR shots_on_target_against >= 0),
            ADD CONSTRAINT check_corners_for CHECK (corners_for IS NULL OR corners_for >= 0),
            ADD CONSTRAINT check_corners_against CHECK (corners_against IS NULL OR corners_against >= 0),
            ADD CONSTRAINT check_fouls_for CHECK (fouls_for IS NULL OR fouls_for >= 0),
            ADD CONSTRAINT check_fouls_against CHECK (fouls_against IS NULL OR fouls_against >= 0),
            ADD CONSTRAINT check_yellow_cards CHECK (yellow_cards IS NULL OR yellow_cards >= 0),
            ADD CONSTRAINT check_red_cards CHECK (red_cards IS NULL OR red_cards >= 0);
    END IF;
END $$;

-- Index for shot-heavy analysis queries
CREATE INDEX IF NOT EXISTS idx_matches_shots_for ON pl_data.matches(shots_for) WHERE shots_for IS NOT NULL;

DO $$
BEGIN
    RAISE NOTICE 'Added match stats columns (shots, corners, fouls, cards) to pl_data.matches';
END $$;
