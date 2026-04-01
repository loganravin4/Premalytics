-- ============================================================================
-- File: 01_create_dimensions.sql
-- Description: Creates core dimension tables (teams, seasons, players)
-- Dependencies: None (first file to run)
-- Schema: pl_data
-- ============================================================================

-- ============================================================================
-- DATABASE CREATION
-- ============================================================================
-- Create database if it doesn't exist
-- Note: This must be run as a superuser and requires connecting to 'postgres' database first
-- In pgAdmin: Connect to 'postgres' database, then run this section separately
-- For automated scripts: Handle database creation separately before running schema files

-- To create database manually in pgAdmin:
-- 1. Right-click on 'Databases' → Create → Database
-- 2. Name: premalytics_db
-- 3. Owner: postgres (or your user)
-- Or execute this in postgres database:
-- CREATE DATABASE premalytics_db WITH ENCODING='UTF8' LC_COLLATE='en_US.UTF-8' LC_CTYPE='en_US.UTF-8';

-- ============================================================================
-- SCHEMA CREATION
-- ============================================================================
-- Connect to premalytics_db database first, then run the rest of this file

-- Drop schema if exists (for clean reinstalls)
DROP SCHEMA IF EXISTS pl_data CASCADE;

-- Create pl_data schema for all Premier League data
CREATE SCHEMA pl_data;

-- Set search path so we don't need to prefix pl_data every time
-- This is session-specific, so scripts should set it at the beginning
SET search_path TO pl_data, public;

-- ============================================================================
-- DIMENSION TABLE: teams
-- Description: All Premier League teams across all seasons
-- Primary Key: team_id (FBRef's unique team identifier)
-- ============================================================================
CREATE TABLE pl_data.teams (
    team_id VARCHAR(50) PRIMARY KEY,          -- FBRef team ID (e.g., 'b8fd03ef' for Liverpool)
    team_name VARCHAR(100) NOT NULL,          -- Full team name (e.g., 'Liverpool', 'Manchester City')
    team_url VARCHAR(255),                     -- FBRef URL: /en/squads/{team_id}/...
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add comment to table
COMMENT ON TABLE pl_data.teams IS 'Premier League teams across all seasons';
COMMENT ON COLUMN pl_data.teams.team_id IS 'FBRef unique team identifier extracted from URLs';
COMMENT ON COLUMN pl_data.teams.team_name IS 'Official team name as displayed on FBRef';

-- ============================================================================
-- DIMENSION TABLE: seasons
-- Description: Premier League seasons (e.g., 2023-2024)
-- Primary Key: season_id
-- ============================================================================
CREATE TABLE pl_data.seasons (
    season_id VARCHAR(20) PRIMARY KEY,        -- Format: 'YYYY-YYYY' (e.g., '2023-2024')
    start_year INTEGER NOT NULL,              -- Starting year (e.g., 2023)
    end_year INTEGER NOT NULL,                -- Ending year (e.g., 2024)
    
    -- Data quality flags
    is_complete BOOLEAN DEFAULT TRUE,         -- FALSE if season has incomplete data
    data_collection_date DATE,                -- When data was last scraped for this season
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT check_year_order CHECK (end_year = start_year + 1),
    CONSTRAINT check_season_format CHECK (season_id ~ '^\d{4}-\d{4}$')
);

-- Add comments
COMMENT ON TABLE pl_data.seasons IS 'Premier League seasons from 2021-2022 through 2024-2025';
COMMENT ON COLUMN pl_data.seasons.is_complete IS 'FALSE for 2025-2026 which has incomplete stat categories';
COMMENT ON COLUMN pl_data.seasons.data_collection_date IS 'Last scrape date for tracking data freshness';

-- ============================================================================
-- DIMENSION TABLE: players
-- Description: Players who appeared for teams in specific seasons
-- Primary Key: player_season_id (surrogate key)
-- Natural Key: (player_id, team_id, season_id)
-- Note: A player can appear multiple times if they change teams between seasons
-- ============================================================================
CREATE TABLE pl_data.players (
    player_season_id SERIAL PRIMARY KEY,      -- Surrogate key for easier joins
    
    -- Player identification
    player_id VARCHAR(50) NOT NULL,           -- FBRef player ID (e.g., 'e342ad68' for Salah)
    player_name VARCHAR(100) NOT NULL,        -- Full player name (e.g., 'Mohamed Salah')
    player_url VARCHAR(255),                   -- FBRef URL: /en/players/{player_id}/...
    
    -- Team and season association
    team_id VARCHAR(50) NOT NULL,             -- Which team the player played for this season
    season_id VARCHAR(20) NOT NULL,           -- Which season
    
    -- Player attributes
    nationality VARCHAR(50),                  -- Nationality code (e.g., 'egEGY' for Egypt)
    position VARCHAR(20),                     -- Primary position: 'FW', 'MF', 'DF', 'GK'
    age INTEGER,                              -- Player's age during this season
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    CONSTRAINT fk_players_team FOREIGN KEY (team_id) 
        REFERENCES pl_data.teams(team_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_players_season FOREIGN KEY (season_id) 
        REFERENCES pl_data.seasons(season_id) 
        ON DELETE CASCADE,
    
    -- Constraints
    CONSTRAINT unique_player_team_season UNIQUE (player_id, team_id, season_id),
    CONSTRAINT check_position CHECK (position IS NULL OR LENGTH(position) > 0),
    CONSTRAINT check_age CHECK (age BETWEEN 15 AND 45)
);

-- Add comments
COMMENT ON TABLE pl_data.players IS 'Players who appeared for teams in specific seasons';
COMMENT ON COLUMN pl_data.players.player_season_id IS 'Surrogate key used throughout the database for joins';
COMMENT ON COLUMN pl_data.players.player_id IS 'FBRef unique player identifier (consistent across seasons)';
COMMENT ON COLUMN pl_data.players.nationality IS 'Two-letter country code + country name (e.g., egEGY)';
COMMENT ON COLUMN pl_data.players.position IS 'Primary position; some players have dual positions like FW,MF';

-- ============================================================================
-- INDEXES FOR DIMENSION TABLES
-- ============================================================================

-- Teams indexes
CREATE INDEX idx_teams_name ON pl_data.teams(team_name);

-- Seasons indexes  
CREATE INDEX idx_seasons_years ON pl_data.seasons(start_year, end_year);
CREATE INDEX idx_seasons_complete ON pl_data.seasons(is_complete);

-- Players indexes
CREATE INDEX idx_players_player_id ON pl_data.players(player_id);
CREATE INDEX idx_players_team ON pl_data.players(team_id);
CREATE INDEX idx_players_season ON pl_data.players(season_id);
CREATE INDEX idx_players_position ON pl_data.players(position);
CREATE INDEX idx_players_team_season ON pl_data.players(team_id, season_id);

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================
DO $$ 
BEGIN 
    RAISE NOTICE 'Successfully created dimension tables in pl_data schema';
    RAISE NOTICE '   - pl_data.teams';
    RAISE NOTICE '   - pl_data.seasons';
    RAISE NOTICE '   - pl_data.players';
    RAISE NOTICE '';
    RAISE NOTICE 'Next step: Run 02_create_matches.sql';
END $$;