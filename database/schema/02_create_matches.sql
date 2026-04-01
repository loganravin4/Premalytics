-- ============================================================================
-- File: 02_create_matches.sql
-- Description: Creates matches fact table for team-level match results
-- Dependencies: 01_create_dimensions.sql (requires teams, seasons)
-- Schema: pl_data
-- ============================================================================

-- Set search path to pl_data schema
SET search_path TO pl_data, public;

-- ============================================================================
-- FACT TABLE: matches
-- Description: Team-level match results and statistics
-- 
-- IMPORTANT: Each match appears TWICE in this table:
--   - Once from the home team's perspective (venue='Home')
--   - Once from the away team's perspective (venue='Away')
-- 
-- This design allows easy querying of team-specific stats:
--   - "Get all Liverpool matches" → WHERE team_id = 'Liverpool'
--   - "Get Liverpool's home record" → WHERE team_id = 'Liverpool' AND venue = 'Home'
--
-- Each team plays 38 Premier League matches per season.
-- Total rows per season: 20 teams × 38 matches = 760 rows
-- Total rows (4 complete seasons): 760 × 4 = 3,040 rows
-- ============================================================================

DROP TABLE IF EXISTS pl_data.matches CASCADE;

CREATE TABLE pl_data.matches (
    -- Primary key
    match_team_id SERIAL PRIMARY KEY,         -- Surrogate key (auto-incrementing)
    
    -- Match identification
    match_id VARCHAR(50) NOT NULL,            -- FBRef match ID (e.g., 'c18d3207')
    season_id VARCHAR(20) NOT NULL,           -- Which season (e.g., '2023-2024')
    team_id VARCHAR(50) NOT NULL,             -- The team from whose perspective we're viewing
    
    -- ========================================================================
    -- TEMPORAL INFORMATION
    -- ========================================================================
    match_date DATE NOT NULL,                 -- Match date (e.g., '2023-08-13')
    start_time TIME,                          -- Kickoff time (e.g., '16:30:00')
    round VARCHAR(50),                        -- Round name (e.g., 'Matchweek 1', 'Matchweek 38')
    day_of_week VARCHAR(20),                  -- Day match was played (e.g., 'Saturday', 'Sunday')
    
    -- ========================================================================
    -- LOCATION AND OPPONENT
    -- ========================================================================
    venue VARCHAR(10) NOT NULL,               -- 'Home' or 'Away' from team_id's perspective
    opponent_id VARCHAR(50) NOT NULL,         -- The opposing team's ID
    opponent_url VARCHAR(255),                -- FBRef URL for opponent
    
    -- ========================================================================
    -- MATCH RESULT
    -- ========================================================================
    result CHAR(1) NOT NULL,                  -- 'W' = Win, 'D' = Draw, 'L' = Loss
    goals_for INTEGER NOT NULL,               -- Goals scored by team_id
    goals_against INTEGER NOT NULL,           -- Goals conceded by team_id
    
    -- Expected Goals (xG) - Key metric for match quality
    xg_for DECIMAL(5,2),                      -- Expected goals for team_id (e.g., 2.30)
    xg_against DECIMAL(5,2),                  -- Expected goals for opponent (e.g., 1.40)
    
    -- ========================================================================
    -- MATCH DETAILS
    -- ========================================================================
    possession INTEGER,                       -- Possession percentage (0-100)
    attendance VARCHAR(20),                   -- Match attendance (e.g., '40,096')
    
    -- Team information
    captain VARCHAR(100),                     -- Team captain for this match
    formation VARCHAR(20),                    -- Team's formation (e.g., '4-3-3', '3-4-3')
    opp_formation VARCHAR(20),                -- Opponent's formation
    
    -- Match officials
    referee VARCHAR(100),                     -- Match referee name
    
    -- URLs and additional info
    match_report_url VARCHAR(255),            -- Link to FBRef match report
    notes TEXT,                               -- Any additional notes (usually NULL)
    
    -- ========================================================================
    -- METADATA
    -- ========================================================================
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- ========================================================================
    -- FOREIGN KEY CONSTRAINTS
    -- ========================================================================
    CONSTRAINT fk_matches_season FOREIGN KEY (season_id) 
        REFERENCES pl_data.seasons(season_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_matches_team FOREIGN KEY (team_id) 
        REFERENCES pl_data.teams(team_id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_matches_opponent FOREIGN KEY (opponent_id) 
        REFERENCES pl_data.teams(team_id) 
        ON DELETE CASCADE,
    
    -- ========================================================================
    -- DATA INTEGRITY CONSTRAINTS
    -- ========================================================================
    
    -- Ensure each match appears only once per team
    CONSTRAINT unique_match_team UNIQUE (match_id, team_id),
    
    -- Venue must be Home or Away
    CONSTRAINT check_venue CHECK (venue IN ('Home', 'Away')),
    
    -- Result must be W, D, or L
    CONSTRAINT check_result CHECK (result IN ('W', 'D', 'L')),
    
    -- Goals must be non-negative
    CONSTRAINT check_goals_for CHECK (goals_for >= 0),
    CONSTRAINT check_goals_against CHECK (goals_against >= 0),
    
    -- xG must be non-negative (can be NULL)
    CONSTRAINT check_xg_for CHECK (xg_for IS NULL OR xg_for >= 0),
    CONSTRAINT check_xg_against CHECK (xg_against IS NULL OR xg_against >= 0),
    
    -- Possession must be between 0 and 100 (can be NULL)
    CONSTRAINT check_possession CHECK (possession IS NULL OR (possession >= 0 AND possession <= 100)),
    
    -- Team cannot play itself
    CONSTRAINT check_not_self_match CHECK (team_id != opponent_id),
    
    -- Result consistency: Win means goals_for > goals_against
    CONSTRAINT check_result_consistency CHECK (
        (result = 'W' AND goals_for > goals_against) OR
        (result = 'D' AND goals_for = goals_against) OR
        (result = 'L' AND goals_for < goals_against)
    )
);

-- ============================================================================
-- TABLE COMMENTS (Documentation)
-- ============================================================================
COMMENT ON TABLE pl_data.matches IS 
'Team-level match results. Each physical match appears twice (once per team).';

COMMENT ON COLUMN pl_data.matches.match_team_id IS 
'Surrogate primary key (auto-incrementing). Use for joins in analysis.';

COMMENT ON COLUMN pl_data.matches.match_id IS 
'FBRef unique match identifier. Same match_id appears twice (home + away team rows).';

COMMENT ON COLUMN pl_data.matches.team_id IS 
'The team from whose perspective this row shows the match (references teams.team_id).';

COMMENT ON COLUMN pl_data.matches.venue IS 
'Home or Away from team_id perspective. Liverpool at Anfield = Home, Liverpool at Old Trafford = Away.';

COMMENT ON COLUMN pl_data.matches.result IS 
'Match result from team_id perspective. W=Win, D=Draw, L=Loss.';

COMMENT ON COLUMN pl_data.matches.goals_for IS 
'Goals scored BY team_id in this match.';

COMMENT ON COLUMN pl_data.matches.goals_against IS 
'Goals scored AGAINST team_id (conceded) in this match.';

COMMENT ON COLUMN pl_data.matches.xg_for IS 
'Expected Goals (xG) for team_id. Measures shot quality. Higher = better attacking performance.';

COMMENT ON COLUMN pl_data.matches.xg_against IS 
'Expected Goals (xG) against team_id. Measures opponent shot quality. Lower = better defensive performance.';

COMMENT ON COLUMN pl_data.matches.possession IS 
'Ball possession percentage for team_id (0-100). Higher = more control.';

COMMENT ON COLUMN pl_data.matches.formation IS 
'Tactical formation used by team_id (e.g., 4-3-3, 3-4-3, 4-2-3-1).';

COMMENT ON COLUMN pl_data.matches.attendance IS 
'Match attendance as string with commas (e.g., 53,145). Convert to integer for analysis.';

-- ============================================================================
-- INDEXES FOR QUERY PERFORMANCE
-- ============================================================================

-- Most common query: Get all matches for a specific team
CREATE INDEX idx_matches_team_id ON pl_data.matches(team_id);

-- Get matches for a specific season
CREATE INDEX idx_matches_season_id ON pl_data.matches(season_id);

-- Get matches against a specific opponent
CREATE INDEX idx_matches_opponent_id ON pl_data.matches(opponent_id);

-- Temporal queries: Find matches by date
CREATE INDEX idx_matches_date ON pl_data.matches(match_date);

-- Venue splits: Home vs Away performance
CREATE INDEX idx_matches_venue ON pl_data.matches(venue);

-- Result analysis: Wins, Draws, Losses
CREATE INDEX idx_matches_result ON pl_data.matches(result);

-- Composite indexes for common filtered queries
CREATE INDEX idx_matches_team_season ON pl_data.matches(team_id, season_id);
CREATE INDEX idx_matches_team_venue ON pl_data.matches(team_id, venue);
CREATE INDEX idx_matches_season_date ON pl_data.matches(season_id, match_date);

-- Match lookup: Find both perspectives of the same match
CREATE INDEX idx_matches_match_id ON pl_data.matches(match_id);

-- ============================================================================
-- EXAMPLE QUERIES (for documentation/testing)
-- ============================================================================

-- Query 1: Get all Liverpool home matches in 2023-2024
-- SELECT * FROM pl_data.matches 
-- WHERE team_id = 'b8fd03ef' 
--   AND season_id = '2023-2024' 
--   AND venue = 'Home'
-- ORDER BY match_date;

-- Query 2: Get Liverpool's record vs Manchester City (all seasons)
-- SELECT 
--     season_id,
--     match_date,
--     venue,
--     result,
--     goals_for,
--     goals_against,
--     xg_for,
--     xg_against
-- FROM pl_data.matches 
-- WHERE team_id = 'b8fd03ef'  -- Liverpool
--   AND opponent_id = 'b8fd03ef'  -- Man City ID would go here
-- ORDER BY match_date;

-- Query 3: Calculate team's season win rate
-- SELECT 
--     team_id,
--     season_id,
--     COUNT(*) as total_matches,
--     SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) as wins,
--     ROUND(SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100, 2) as win_rate
-- FROM pl_data.matches
-- GROUP BY team_id, season_id
-- ORDER BY win_rate DESC;

-- Query 4: Find high-scoring matches (both teams scored 3+)
-- SELECT 
--     m1.match_date,
--     t1.team_name as home_team,
--     m1.goals_for as home_goals,
--     t2.team_name as away_team,
--     m1.goals_against as away_goals
-- FROM pl_data.matches m1
-- JOIN pl_data.teams t1 ON m1.team_id = t1.team_id
-- JOIN pl_data.teams t2 ON m1.opponent_id = t2.team_id
-- WHERE m1.venue = 'Home'
--   AND m1.goals_for >= 3
--   AND m1.goals_against >= 3
-- ORDER BY (m1.goals_for + m1.goals_against) DESC;

-- ============================================================================
-- DATA VALIDATION VIEWS (Optional - for quality checks)
-- ============================================================================

-- Create view to check for missing opponent records
CREATE OR REPLACE VIEW pl_data.v_match_data_quality AS
SELECT 
    season_id,
    COUNT(*) as total_matches,
    COUNT(CASE WHEN xg_for IS NULL THEN 1 END) as missing_xg_for,
    COUNT(CASE WHEN xg_against IS NULL THEN 1 END) as missing_xg_against,
    COUNT(CASE WHEN possession IS NULL THEN 1 END) as missing_possession,
    COUNT(CASE WHEN formation IS NULL THEN 1 END) as missing_formation
FROM pl_data.matches
GROUP BY season_id
ORDER BY season_id;

COMMENT ON VIEW pl_data.v_match_data_quality IS 
'Data quality check: Shows count of NULL values per season for key match statistics.';

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================
DO $$ 
BEGIN 
    RAISE NOTICE 'Successfully created matches fact table in pl_data schema';
    RAISE NOTICE '   - pl_data.matches';
    RAISE NOTICE '   - pl_data.v_match_data_quality (data quality view)';
    RAISE NOTICE '';
    RAISE NOTICE 'Table design:';
    RAISE NOTICE '   - Each match appears TWICE (once per team)';
    RAISE NOTICE '   - Expected rows per season: 760 (20 teams × 38 matches)';
    RAISE NOTICE '   - Expected total rows: ~3,040 (4 complete seasons)';
    RAISE NOTICE '';
    RAISE NOTICE 'Performance indexes created:';
    RAISE NOTICE '   - 11 indexes for optimized queries';
    RAISE NOTICE '';
    RAISE NOTICE 'Next step: Run 03_create_player_stats.sql';
END $$;